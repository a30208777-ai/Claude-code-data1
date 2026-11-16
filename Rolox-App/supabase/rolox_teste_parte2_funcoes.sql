-- =====================================================================
-- ROLOX — PARTE 2: funções (cole no SQL Editor do projeto Rolox e clique em Run)
-- A parte 1 (tabelas, RLS, Realtime) já foi aplicada.
-- Se o Supabase avisar sobre comandos "destrutivos", pode confirmar: são os
-- DELETE de dentro das funções (sair do servidor, limpezas), não apagam nada agora.
-- =====================================================================

-- Cria o perfil automaticamente no cadastro (username vem do metadata)
create function public.criar_perfil_novo_usuario()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.perfis (id, username, aceitou_localizacao)
  values (
    new.id,
    lower(new.raw_user_meta_data ->> 'username'),
    coalesce((new.raw_user_meta_data ->> 'aceitou_localizacao')::boolean, false)
  );
  return new;
end $$;

create trigger ao_criar_usuario
  after insert on auth.users
  for each row execute function public.criar_perfil_novo_usuario();

-- =====================================================================
-- Funções (RPC)
-- =====================================================================

-- Filtro local: remove o termo e a palavra de ligação solta antes dele
-- ("a porra de uma sacola" -> "uma sacola"), preservando o resto da frase.
create function public.filtrar_texto(p_texto text)
returns text language plpgsql stable set search_path = public as $$
declare
  t record;
  r text := p_texto;
begin
  for t in select termo from public.termos_bloqueados loop
    -- "a/o/uma/um <termo> de/do/da" some inteiro
    r := regexp_replace(r, '\m(a|o|uma|um)\s+' || t.termo || '\s+(de|do|da)\s+', '', 'gi');
    r := regexp_replace(r, '\m' || t.termo || '\s+(de|do|da)\s+', '', 'gi');
    r := regexp_replace(r, '\m' || t.termo || '\M', '', 'gi');
  end loop;
  r := regexp_replace(r, '\s{2,}', ' ', 'g');
  r := regexp_replace(r, '\s+([,.!?;:])', '\1', 'g');
  r := regexp_replace(r, '^[\s,.;:]+', '');
  return btrim(r);
end $$;

-- Matchmaking (Fase 12): retorna null se pode entrar, ou o motivo do bloqueio
create function public.motivo_bloqueio(p_user uuid, p_server public.servidores_ativos)
returns text language sql stable set search_path = public as $$
  select case
    when p.banido then 'conta_banida'
    when p.jogo_mod is not distinct from p_server.gameid and not p_server.is_hack_server
      then 'use_servidor_hack'
    when p_server.is_hack_server and p.jogo_mod is distinct from p_server.gameid
      then 'servidor_so_para_hack'
    else null
  end
  from public.perfis p where p.id = p_user
$$;

-- Fase 8: entrar com checagem de capacidade sob lock; cheio -> fila
create function public.entrar_servidor(p_server uuid)
returns json language plpgsql security definer set search_path = public as $$
declare
  s public.servidores_ativos;
  uid uuid := auth.uid();
  motivo text;
  ocupados int;
  antigo record;
begin
  if uid is null then raise exception 'não autenticado'; end if;

  select * into s from public.servidores_ativos where server_uid = p_server for update;
  if not found or s.status = 'encerrando' then
    return json_build_object('resultado', 'servidor_inexistente');
  end if;

  motivo := public.motivo_bloqueio(uid, s);
  if motivo is not null then
    return json_build_object('resultado', motivo);
  end if;

  if exists (select 1 from public.users_dos_servidores where server_uid = p_server and user_id = uid) then
    return json_build_object('resultado', 'ja_esta');
  end if;

  -- só pode estar em um servidor (e uma fila) por vez: sai dos outros antes
  for antigo in
    select server_uid from public.users_dos_servidores where user_id = uid and server_uid <> p_server
    union
    select server_uid from public.espera where user_id = uid and server_uid <> p_server
  loop
    perform public.sair_servidor(antigo.server_uid);
  end loop;

  select count(*) into ocupados from public.users_dos_servidores where server_uid = p_server;

  if ocupados < s.capacidade then
    insert into public.users_dos_servidores (server_uid, user_id) values (p_server, uid);
    if ocupados + 1 >= s.capacidade then
      update public.servidores_ativos set status = 'cheio' where server_uid = p_server;
    end if;
    perform public.registrar_local(uid, case when s.is_hack_server then 'hack' else 'jogo' end, p_server);
    return json_build_object('resultado', 'entrou');
  end if;

  insert into public.espera (server_uid, user_id) values (p_server, uid);
  perform public.registrar_local(uid, 'fila', p_server);
  return json_build_object(
    'resultado', 'fila',
    'posicao', (select count(*) from public.espera where server_uid = p_server));
end $$;

-- Sai do servidor (ou da fila) e promove o primeiro da fila que puder entrar
create function public.sair_servidor(p_server uuid)
returns json language plpgsql security definer set search_path = public as $$
declare
  s public.servidores_ativos;
  uid uuid := auth.uid();
  prox record;
begin
  if uid is null then raise exception 'não autenticado'; end if;

  select * into s from public.servidores_ativos where server_uid = p_server for update;
  delete from public.espera where server_uid = p_server and user_id = uid;
  delete from public.users_dos_servidores where server_uid = p_server and user_id = uid;
  perform public.registrar_local(uid, 'lobby', null);

  if s.server_uid is not null then
    for prox in
      select e.id, e.user_id from public.espera e
      where e.server_uid = p_server order by e.entrou_em, e.id
    loop
      exit when (select count(*) from public.users_dos_servidores where server_uid = p_server) >= s.capacidade;
      delete from public.espera where id = prox.id;
      if public.motivo_bloqueio(prox.user_id, s) is null then
        insert into public.users_dos_servidores (server_uid, user_id) values (p_server, prox.user_id);
        perform public.registrar_local(prox.user_id, case when s.is_hack_server then 'hack' else 'jogo' end, p_server);
      end if;
    end loop;

    update public.servidores_ativos
       set status = case when (select count(*) from public.users_dos_servidores where server_uid = p_server) >= capacidade
                         then 'cheio' else 'aberto' end
     where server_uid = p_server;
  end if;

  return json_build_object('resultado', 'saiu');
end $$;

-- Fase 9: só grava localização com consentimento (LGPD)
create function public.registrar_local(p_user uuid, p_locate text, p_server uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from public.perfis where id = p_user and aceitou_localizacao) then
    insert into public.locate_users (user_id, locate, server_uid, atualizado_em)
    values (p_user, p_locate, p_server, now())
    on conflict (user_id) do update
      set locate = excluded.locate, server_uid = excluded.server_uid, atualizado_em = now();
  else
    delete from public.locate_users where user_id = p_user;
  end if;
end $$;

create function public.atualizar_local(p_locate text)
returns void language sql security definer set search_path = public as $$
  select public.registrar_local(auth.uid(), p_locate,
    (select server_uid from public.users_dos_servidores where user_id = auth.uid() limit 1));
$$;

-- Fase 16: chat com filtro local; anti-spam de 1 mensagem/segundo
create function public.enviar_mensagem(p_server uuid, p_texto text, p_idioma text default null)
returns json language plpgsql security definer set search_path = public as $$
declare
  uid uuid := auth.uid();
  nome text;
  filtrada text;
begin
  if uid is null then raise exception 'não autenticado'; end if;
  if not exists (select 1 from public.users_dos_servidores where server_uid = p_server and user_id = uid) then
    return json_build_object('resultado', 'fora_do_servidor');
  end if;
  if exists (select 1 from public.servidores_logados
             where user_id = uid and criado_em > now() - interval '1 second') then
    return json_build_object('resultado', 'muito_rapido');
  end if;

  p_texto := btrim(coalesce(p_texto, ''));
  if char_length(p_texto) = 0 or char_length(p_texto) > 500 then
    return json_build_object('resultado', 'tamanho_invalido');
  end if;

  select username into nome from public.perfis where id = uid;
  filtrada := public.filtrar_texto(p_texto);

  insert into public.servidores_logados (server_uid, user_id, username, mensagem_original, mensagem_filtrada, idioma_original)
  values (p_server, uid, nome, p_texto, filtrada, p_idioma);
  return json_build_object('resultado', 'enviada', 'mensagem_filtrada', filtrada);
end $$;

-- Fase 10: trocou o jogo de hack/mod no meio da partida -> desconexão limpa
-- de servidores e filas que ficaram incompatíveis.
create function public.ao_trocar_jogo_mod()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  srv public.servidores_ativos;
begin
  for srv in
    select s.* from public.servidores_ativos s
     where s.server_uid in (
       select server_uid from public.users_dos_servidores where user_id = new.id
       union
       select server_uid from public.espera where user_id = new.id)
  loop
    if public.motivo_bloqueio(new.id, srv) is not null then
      delete from public.users_dos_servidores where server_uid = srv.server_uid and user_id = new.id;
      delete from public.espera where server_uid = srv.server_uid and user_id = new.id;
      update public.servidores_ativos set status = 'aberto'
       where server_uid = srv.server_uid and status = 'cheio';
      perform public.registrar_local(new.id, 'lobby', null);
    end if;
  end loop;
  return new;
end $$;

create trigger ao_trocar_jogo_mod
  after update of jogo_mod on public.perfis
  for each row when (old.jogo_mod is distinct from new.jogo_mod)
  execute function public.ao_trocar_jogo_mod();

-- Fase 7: limpeza de servidores sem heartbeat (agendar com pg_cron a cada minuto)
create function public.limpar_servidores_inativos()
returns int language plpgsql security definer set search_path = public as $$
declare n int;
begin
  delete from public.servidores_ativos s
   where s.ultimo_heartbeat < now() - interval '60 seconds'
      or (s.criado_em < now() - interval '5 minutes'
          and not exists (select 1 from public.users_dos_servidores u where u.server_uid = s.server_uid));
  get diagnostics n = row_count;
  return n;
end $$;

-- LGPD: apaga dados sensíveis com mais de 30 dias
create function public.limpar_dados_antigos()
returns void language sql security definer set search_path = public as $$
  delete from public.tentativas_login  where criado_em < now() - interval '30 days';
  delete from public.alertas_seguranca where criado_em < now() - interval '30 days';
  update public.servidores_logados set mensagem_original = mensagem_filtrada
   where criado_em < now() - interval '30 days' and mensagem_original <> mensagem_filtrada;
$$;

-- =====================================================================
-- Agendamentos (pg_cron, se estiver ativo no projeto)
-- =====================================================================
do $$ begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('rolox-limpar-servidores', '* * * * *', 'select public.limpar_servidores_inativos()');
    perform cron.schedule('rolox-limpar-dados', '17 3 * * *', 'select public.limpar_dados_antigos()');
  end if;
end $$;
