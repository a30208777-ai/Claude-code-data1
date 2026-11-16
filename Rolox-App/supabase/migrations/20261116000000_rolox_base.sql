-- ROLOX — esquema base (arquitetura v3)
-- Fases cobertas: 2 (perfis/RLS), 3 (tabelas de segurança do login),
-- 6–9 (tempo real, servidores, fila, localização), 10 (perfil/mod),
-- 12 (matchmaking limpo × hack), 16 (chat com filtro local).

-- =====================================================================
-- Catálogo de jogos/mapas (GitHub) — só aparece depois da aprovação do dono
-- =====================================================================
create table public.jogos (
  gameid           text primary key check (gameid ~ '^[a-z0-9-]{2,40}$'),
  nome             text not null,
  repo             text not null,
  branch           text not null default 'main',
  commit_aprovado  text,
  sha256           text,
  aprovado_por     uuid,
  aprovado_em      timestamptz
);

-- =====================================================================
-- Perfis (ligados ao Supabase Auth)
-- =====================================================================
create table public.perfis (
  id                   uuid primary key references auth.users(id) on delete cascade,
  username             text unique not null
                       check (username ~ '^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$'),
  idioma               text not null default 'pt-BR',
  banido               boolean not null default false,
  motivo_ban           text,
  jogo_mod             text references public.jogos(gameid) on delete set null,
  aceitou_localizacao  boolean not null default false,
  is_admin             boolean not null default false,
  criado_em            timestamptz not null default now()
);

alter table public.jogos
  add constraint jogos_aprovado_por_fk foreign key (aprovado_por) references public.perfis(id);

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
-- Segurança do login (só o backend / Edge Functions acessam)
-- =====================================================================
create table public.ips_bloqueados (
  ip             inet primary key,
  conta_alvo     uuid references public.perfis(id) on delete set null,
  motivo         text not null default '3 tentativas de senha errada',
  bloqueado_por  uuid references public.perfis(id),
  bloqueado_em   timestamptz not null default now()
);

create table public.ips_confiaveis (
  user_id     uuid not null references public.perfis(id) on delete cascade,
  ip          inet not null,
  visto_em    timestamptz not null default now(),
  primary key (user_id, ip)
);

create table public.tentativas_login (
  id                     bigserial primary key,
  conta_alvo             uuid not null references public.perfis(id) on delete cascade,
  ip                     inet not null,
  senha_tentada_cifrada  text not null,   -- base64(iv || AES-GCM(senha))
  criado_em              timestamptz not null default now()
);
create index tentativas_login_conta_ip on public.tentativas_login (conta_alvo, ip, criado_em);

create table public.alertas_seguranca (
  id                     bigserial primary key,
  user_id                uuid not null references public.perfis(id) on delete cascade,
  ip                     inet not null,
  senha_tentada_cifrada  text not null,
  ip_foi_banido          boolean not null default false,
  lido                   boolean not null default false,
  criado_em              timestamptz not null default now()
);
create index alertas_user on public.alertas_seguranca (user_id, criado_em desc);

create table public.credenciais_backup (
  user_id     uuid primary key references public.perfis(id) on delete cascade,
  credencial  text not null,              -- base64(iv || AES-GCM(credencial))
  criado_em   timestamptz not null default now()
);

-- =====================================================================
-- Tempo real
-- =====================================================================
create table public.servidores_ativos (
  server_uid        uuid primary key default gen_random_uuid(),
  gameid            text not null references public.jogos(gameid),
  host_id           uuid not null references public.perfis(id) on delete cascade,
  capacidade        int  not null check (capacidade between 1 and 100),
  is_hack_server    boolean not null default false,
  status            text not null default 'aberto' check (status in ('aberto','cheio','encerrando')),
  ultimo_heartbeat  timestamptz not null default now(),
  criado_em         timestamptz not null default now()
);

create table public.users_dos_servidores (
  server_uid  uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references public.perfis(id) on delete cascade,
  entrou_em   timestamptz not null default now(),
  primary key (server_uid, user_id)
);

create table public.espera (
  id          bigserial primary key,
  server_uid  uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references public.perfis(id) on delete cascade,
  entrou_em   timestamptz not null default now(),
  unique (server_uid, user_id)
);

create table public.locate_users (
  user_id        uuid primary key references public.perfis(id) on delete cascade,
  locate         text not null check (locate in ('menu','lobby','jogo','hack','fila')),
  server_uid     uuid references public.servidores_ativos(server_uid) on delete set null,
  atualizado_em  timestamptz not null default now()
);

create table public.servidores_logados (   -- chat da sessão
  id                 bigserial primary key,
  server_uid         uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  user_id            uuid not null references public.perfis(id) on delete cascade,
  username           text not null,
  mensagem_original  text not null check (char_length(mensagem_original) between 1 and 500),
  mensagem_filtrada  text not null,
  idioma_original    text,
  criado_em          timestamptz not null default now()
);
create index chat_servidor on public.servidores_logados (server_uid, id);

create table public.itens_sessao (
  server_uid  uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references public.perfis(id) on delete cascade,
  item_id     text not null,
  quantidade  int  not null default 1,
  primary key (server_uid, user_id, item_id)
);

-- Termos do filtro local (1º passo antes da IA SELECT)
create table public.termos_bloqueados (
  termo  text primary key
);
-- guardar sempre em minúsculas
insert into public.termos_bloqueados (termo) values
  ('porra'), ('caralho'), ('merda'), ('puta'), ('fdp'), ('vsf'), ('arrombado');

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
-- RLS
-- =====================================================================
alter table public.jogos                enable row level security;
alter table public.perfis               enable row level security;
alter table public.ips_bloqueados       enable row level security;
alter table public.ips_confiaveis       enable row level security;
alter table public.tentativas_login     enable row level security;
alter table public.alertas_seguranca    enable row level security;
alter table public.credenciais_backup   enable row level security;
alter table public.servidores_ativos    enable row level security;
alter table public.users_dos_servidores enable row level security;
alter table public.espera               enable row level security;
alter table public.locate_users         enable row level security;
alter table public.servidores_logados   enable row level security;
alter table public.itens_sessao         enable row level security;
alter table public.termos_bloqueados    enable row level security;

create policy "jogos aprovados são públicos" on public.jogos
  for select using (commit_aprovado is not null);

create policy "perfis visíveis para logados" on public.perfis
  for select to authenticated using (true);
create policy "dono edita o próprio perfil" on public.perfis
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);
-- só estas colunas podem ser alteradas pelo próprio usuário
revoke update on public.perfis from authenticated, anon;
grant update (idioma, jogo_mod, aceitou_localizacao) on public.perfis to authenticated;

create policy "dono vê os próprios alertas" on public.alertas_seguranca
  for select to authenticated using (auth.uid() = user_id);
create policy "dono marca alerta como lido" on public.alertas_seguranca
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
revoke update on public.alertas_seguranca from authenticated, anon;
grant update (lido) on public.alertas_seguranca to authenticated;

create policy "servidores visíveis para logados" on public.servidores_ativos
  for select to authenticated using (true);
create policy "host cria servidor" on public.servidores_ativos
  for insert to authenticated with check (auth.uid() = host_id);
create policy "host atualiza servidor" on public.servidores_ativos
  for update to authenticated using (auth.uid() = host_id) with check (auth.uid() = host_id);
create policy "host encerra servidor" on public.servidores_ativos
  for delete to authenticated using (auth.uid() = host_id);
revoke update on public.servidores_ativos from authenticated, anon;
grant update (status, ultimo_heartbeat) on public.servidores_ativos to authenticated;

create policy "membros visíveis para logados" on public.users_dos_servidores
  for select to authenticated using (true);
create policy "fila visível para logados" on public.espera
  for select to authenticated using (true);
create policy "localização visível para logados" on public.locate_users
  for select to authenticated using (true);

create policy "chat: membros do servidor leem" on public.servidores_logados
  for select to authenticated using (exists (
    select 1 from public.users_dos_servidores u
     where u.server_uid = servidores_logados.server_uid and u.user_id = auth.uid()));
create policy "itens: membros do servidor leem" on public.itens_sessao
  for select to authenticated using (exists (
    select 1 from public.users_dos_servidores u
     where u.server_uid = itens_sessao.server_uid and u.user_id = auth.uid()));

-- Funções: só usuários logados chamam as RPCs públicas
revoke execute on function
  public.criar_perfil_novo_usuario(), public.ao_trocar_jogo_mod(), public.filtrar_texto(text),
  public.motivo_bloqueio(uuid, public.servidores_ativos),
  public.entrar_servidor(uuid), public.sair_servidor(uuid),
  public.registrar_local(uuid, text, uuid), public.atualizar_local(text),
  public.enviar_mensagem(uuid, text, text),
  public.limpar_servidores_inativos(), public.limpar_dados_antigos()
  from public, anon, authenticated;
grant execute on function public.entrar_servidor(uuid), public.sair_servidor(uuid),
  public.enviar_mensagem(uuid, text, text), public.atualizar_local(text)
  to authenticated;

-- =====================================================================
-- Realtime
-- =====================================================================
do $$ begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table
      public.servidores_ativos, public.users_dos_servidores, public.espera,
      public.locate_users, public.servidores_logados, public.itens_sessao,
      public.alertas_seguranca;
  end if;
end $$;

-- =====================================================================
-- Agendamentos (pg_cron, se estiver ativo no projeto)
-- =====================================================================
do $$ begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('rolox-limpar-servidores', '* * * * *', 'select public.limpar_servidores_inativos()');
    perform cron.schedule('rolox-limpar-dados', '17 3 * * *', 'select public.limpar_dados_antigos()');
  end if;
end $$;
