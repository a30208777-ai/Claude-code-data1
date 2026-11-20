-- Punição "sem chat": o ADM tira o chat de um jogador por um tempo, com motivo.
-- Os registros no Discord (webhooks) são feitos pelo app em Python.

alter table public.perfis
  add column sem_chat_ate timestamptz,
  add column sem_chat_motivo text;

-- o jogador não pode tirar a própria punição
create or replace function public.proteger_perfil()
returns trigger language plpgsql as $$
begin
  if current_user in ('authenticated', 'anon') and (
       new.id is distinct from old.id
    or new.username is distinct from old.username
    or new.is_adm is distinct from old.is_adm
    or new.banido is distinct from old.banido
    or new.motivo_ban is distinct from old.motivo_ban
    or new.tickets is distinct from old.tickets
    or new.tickets_ultimo_ganho is distinct from old.tickets_ultimo_ganho
    or new.tickets_ultimo_dia is distinct from old.tickets_ultimo_dia
    or new.sem_chat_ate is distinct from old.sem_chat_ate
    or new.sem_chat_motivo is distinct from old.sem_chat_motivo) then
    raise exception 'campo protegido do perfil' using errcode = '42501';
  end if;
  return new;
end $$;

-- o chat respeita a punição
create or replace function public.enviar_mensagem(p_server uuid, p_texto text, p_idioma text default null)
returns json language plpgsql security definer set search_path = public as $$
declare
  uid uuid := auth.uid();
  nome text;
  filtrada text;
  punicao record;
begin
  if uid is null then raise exception 'não autenticado'; end if;
  if not exists (select 1 from public.users_dos_servidores where server_uid = p_server and user_id = uid) then
    return json_build_object('resultado', 'fora_do_servidor');
  end if;
  select sem_chat_ate, sem_chat_motivo into punicao from public.perfis where id = uid;
  if punicao.sem_chat_ate is not null and punicao.sem_chat_ate > now() then
    return json_build_object('resultado', 'sem_chat', 'ate', punicao.sem_chat_ate, 'motivo', punicao.sem_chat_motivo);
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

create function public.adm_sem_chat(p_user uuid, p_minutos int, p_motivo text default null)
returns json language plpgsql security definer set search_path = public as $$
declare r record;
begin
  perform public.exigir_adm();
  if p_user = auth.uid() then raise exception 'você não pode tirar o próprio chat'; end if;
  if p_minutos is null or p_minutos < 1 or p_minutos > 525600 then
    raise exception 'tempo inválido (1 minuto a 1 ano)';
  end if;
  update public.perfis
     set sem_chat_ate = now() + make_interval(mins => p_minutos),
         sem_chat_motivo = left(coalesce(nullif(btrim(p_motivo), ''), 'sem motivo'), 200)
   where id = p_user
  returning username, sem_chat_ate, sem_chat_motivo into r;
  if not found then raise exception 'usuário não encontrado'; end if;
  return json_build_object('username', r.username, 'ate', r.sem_chat_ate, 'motivo', r.sem_chat_motivo);
end $$;

create function public.adm_com_chat(p_user uuid)
returns json language plpgsql security definer set search_path = public as $$
declare nome text;
begin
  perform public.exigir_adm();
  update public.perfis set sem_chat_ate = null, sem_chat_motivo = null where id = p_user returning username into nome;
  if not found then raise exception 'usuário não encontrado'; end if;
  return json_build_object('username', nome);
end $$;

-- painel ADM mostra quem está sem chat
create or replace function public.adm_painel()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  return json_build_object(
    'totais', json_build_object(
      'usuarios', (select count(*) from public.perfis),
      'servidores', (select count(*) from public.servidores_ativos),
      'ips_bloqueados', (select count(*) from public.ips_bloqueados),
      'alertas_hoje', (select count(*) from public.alertas_seguranca where criado_em > now() - interval '1 day')),
    'usuarios', coalesce((select json_agg(u) from (
        select id, username, tickets, is_adm, banido, motivo_ban, criado_em,
               case when sem_chat_ate > now() then sem_chat_ate end as sem_chat_ate,
               case when sem_chat_ate > now() then sem_chat_motivo end as sem_chat_motivo
          from public.perfis order by criado_em desc limit 200) u), '[]'::json),
    'ips_bloqueados', coalesce((select json_agg(i) from (
        select b.ip::text as ip, p.username as conta_alvo, b.motivo, b.bloqueado_em
          from public.ips_bloqueados b left join public.perfis p on p.id = b.conta_alvo
         order by b.bloqueado_em desc limit 200) i), '[]'::json),
    'servidores', coalesce((select json_agg(s) from (
        select s.server_uid, s.gameid, s.capacidade, s.is_hack_server, s.criado_em,
               (select count(*) from public.users_dos_servidores u where u.server_uid = s.server_uid) as humanos,
               (select count(*) from public.bots_dos_servidores b where b.server_uid = s.server_uid) as ias
          from public.servidores_ativos s order by s.criado_em desc limit 200) s), '[]'::json)
  );
end $$;
