-- 🔐 Servidor privado: quem cria ganha um código de 6 letras; só entra quem usar o código.
-- O BANCO bloqueia quem não tem convite (motivo_bloqueio), mesmo que tente entrar direto.
alter table public.servidores_ativos add column if not exists privado boolean not null default false;

create table if not exists public.servidores_privados (
  server_uid uuid primary key references public.servidores_ativos(server_uid) on delete cascade,
  codigo text not null unique check (codigo ~ '^[A-Z2-9]{6}$'),
  criado_em timestamptz not null default now()
);
create table if not exists public.convites_privados (
  server_uid uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  primary key (server_uid, user_id)
);
alter table public.servidores_privados enable row level security;
alter table public.convites_privados enable row level security;

create or replace function public.motivo_bloqueio(p_user uuid, p_server public.servidores_ativos)
returns text language sql stable set search_path = public as $$
  select case
    when p.banido then 'conta_banida'
    when exists (select 1 from public.config_servidor c where c.nome = 'dono_username' and c.valor = p.username)
      then null
    when p_server.privado and not exists (select 1 from public.convites_privados cv
                                           where cv.server_uid = p_server.server_uid and cv.user_id = p_user)
      then 'servidor_privado'
    when p.jogo_mod is not distinct from p_server.gameid and not p_server.is_hack_server
      then 'use_servidor_hack'
    when p_server.is_hack_server and p.jogo_mod is distinct from p_server.gameid
      then 'servidor_so_para_hack'
    else null
  end
  from public.perfis p where p.id = p_user
$$;

create or replace function public.criar_servidor_privado(p_gameid text, p_hack boolean default false)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare eu uuid := auth.uid(); uid uuid; cod text; alfabeto constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; i int; b bytea;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if not exists (select 1 from public.jogos where gameid = p_gameid) then raise exception 'jogo não encontrado' using errcode = 'P0001'; end if;
  if (select count(*) from public.servidores_ativos where host_id = eu and privado) >= 3 then
    raise exception 'você já tem 3 servidores privados abertos' using errcode = 'P0001';
  end if;
  loop
    b := gen_random_bytes(6); cod := '';
    for i in 0..5 loop cod := cod || substr(alfabeto, (get_byte(b, i) % 32) + 1, 1); end loop;
    exit when not exists (select 1 from public.servidores_privados where codigo = cod);
  end loop;
  insert into public.servidores_ativos (gameid, host_id, capacidade, is_hack_server, privado)
  values (p_gameid, eu, 20, coalesce(p_hack, false), true) returning server_uid into uid;
  insert into public.servidores_privados (server_uid, codigo) values (uid, cod);
  insert into public.convites_privados (server_uid, user_id) values (uid, eu);
  return json_build_object('server_uid', uid, 'codigo', cod);
end $$;

create or replace function public.usar_codigo_privado(p_codigo text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); sp public.servidores_privados; g text;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select * into sp from public.servidores_privados where codigo = upper(trim(coalesce(p_codigo, '')));
  if not found then raise exception 'código inválido ou o servidor já fechou' using errcode = 'P0001'; end if;
  insert into public.convites_privados (server_uid, user_id) values (sp.server_uid, eu) on conflict do nothing;
  select gameid into g from public.servidores_ativos where server_uid = sp.server_uid;
  return json_build_object('server_uid', sp.server_uid, 'gameid', g);
end $$;

create or replace function public.codigo_do_meu_privado(p_server uuid)
returns text language sql stable security definer set search_path = public as $$
  select sp.codigo from public.servidores_privados sp
   join public.convites_privados cv on cv.server_uid = sp.server_uid and cv.user_id = auth.uid()
  where sp.server_uid = p_server
$$;
