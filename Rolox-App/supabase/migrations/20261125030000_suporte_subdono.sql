-- 🆘 Suporte (/suport) + 💎 sub dono + selos de cargo (dono 👑💎, sub dono 💎, ADM: logo).

-- ------------------------------------------------------------------ sub dono
create table if not exists public.subdonos (
  username text primary key,
  desde timestamptz not null default now()
);
alter table public.subdonos enable row level security;

create or replace function public.eh_subdono()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.perfis p join public.subdonos s on s.username = p.username
                  where p.id = auth.uid() and not p.banido)
$$;

-- O dono dá ou tira o cargo. O dono nunca vira sub dono dele mesmo (não precisa).
create or replace function public.dono_definir_subdono(p_username text, p_sim boolean)
returns json language plpgsql security definer set search_path = public as $$
declare u text := lower(trim(coalesce(p_username, '')));
begin
  perform public.exigir_dono();
  if not exists (select 1 from public.perfis where username = u) then raise exception 'jogador não encontrado'; end if;
  if p_sim then insert into public.subdonos (username) values (u) on conflict do nothing;
  else delete from public.subdonos where username = u; end if;
  return json_build_object('username', u, 'subdono', p_sim);
end $$;

create or replace function public.listar_subdonos()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  return coalesce((select json_agg(username order by username) from public.subdonos), '[]'::json);
end $$;

-- Cargo público de um jogador (para o selo no perfil): 'dono' | 'subdono' | 'adm' | null
create or replace function public.cargo_de(p_username text)
returns text language sql stable security definer set search_path = public as $$
  select case
    when exists (select 1 from public.config_servidor where nome = 'dono_username' and valor = lower(trim(p_username))) then 'dono'
    when exists (select 1 from public.subdonos where username = lower(trim(p_username))) then 'subdono'
    when exists (select 1 from public.perfis where username = lower(trim(p_username)) and is_adm) then 'adm'
  end
$$;

-- ------------------------------------------------------------------ suporte
create table if not exists public.suporte (
  id bigint generated always as identity primary key,
  user_id uuid references public.perfis(id) on delete cascade,
  username text not null,
  tipo text not null check (tipo in ('bug', 'conta', 'jogo', 'outro', 'ban_injusto')),
  texto text not null check (char_length(texto) between 5 and 1500),
  motivo_ban text,                                   -- foto do motivo do ban (1 pedido por banimento)
  status text not null default 'aberto' check (status in ('aberto', 'respondido', 'fechado')),
  resposta text,
  respondido_por text,
  criado_em timestamptz not null default now(),
  respondido_em timestamptz
);
create index if not exists suporte_status on public.suporte (status, criado_em desc);
alter table public.suporte enable row level security;

create or replace function public.eh_equipe()
returns boolean language sql stable security definer set search_path = public as $$
  select public.eh_dono() or public.eh_subdono() or public.eh_adm()
$$;

-- Jogador logado abre um pedido (máx. 3 abertos ao mesmo tempo).
create or replace function public.abrir_suporte(p_tipo text, p_texto text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); nome text; novo bigint;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if p_tipo not in ('bug', 'conta', 'jogo', 'outro') then raise exception 'tipo inválido'; end if;
  select username into nome from public.perfis where id = eu;
  if (select count(*) from public.suporte where user_id = eu and status = 'aberto') >= 3 then
    raise exception 'você já tem 3 pedidos abertos; espere a resposta';
  end if;
  insert into public.suporte (user_id, username, tipo, texto) values (eu, nome, p_tipo, left(trim(p_texto), 1500))
  returning id into novo;
  return json_build_object('id', novo);
end $$;

-- Conta banida: só o site (com a chave do servidor) abre, e só depois de conferir a senha.
-- 1 pedido "ban injusto" por banimento (por motivo de ban).
create or replace function public.abrir_suporte_ban(p_username text, p_texto text, p_chave text)
returns json language plpgsql security definer set search_path = public as $$
declare p public.perfis%rowtype; novo bigint;
begin
  if p_chave is null or p_chave is distinct from (select valor from public.config_servidor where nome = 'proxy_chave') then
    raise exception 'chave inválida' using errcode = '42501';
  end if;
  select * into p from public.perfis where username = lower(trim(coalesce(p_username, '')));
  if p.id is null or not p.banido then raise exception 'essa conta não está banida'; end if;
  if exists (select 1 from public.suporte where user_id = p.id and tipo = 'ban_injusto'
              and motivo_ban is not distinct from p.motivo_ban) then
    raise exception 'você já pediu revisão deste banimento';
  end if;
  insert into public.suporte (user_id, username, tipo, texto, motivo_ban)
  values (p.id, p.username, 'ban_injusto', left(trim(p_texto), 1500), p.motivo_ban) returning id into novo;
  return json_build_object('id', novo);
end $$;

-- Já pediu revisão deste ban? (para a tela do banido)
create or replace function public.ban_ja_pediu(p_username text, p_chave text)
returns boolean language plpgsql stable security definer set search_path = public as $$
declare p public.perfis%rowtype;
begin
  if p_chave is null or p_chave is distinct from (select valor from public.config_servidor where nome = 'proxy_chave') then
    raise exception 'chave inválida' using errcode = '42501';
  end if;
  select * into p from public.perfis where username = lower(trim(coalesce(p_username, '')));
  return exists (select 1 from public.suporte where user_id = p.id and tipo = 'ban_injusto'
                  and motivo_ban is not distinct from p.motivo_ban);
end $$;

create or replace function public.meus_suportes()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  return coalesce((select json_agg(x order by x.criado_em desc) from (
    select id, tipo, texto, status, resposta, criado_em, respondido_em from public.suporte
     where user_id = auth.uid() order by criado_em desc limit 30) x), '[]'::json);
end $$;

-- Equipe (dono, sub dono, ADM) vê e responde.
create or replace function public.listar_suporte(p_status text default 'aberto')
returns json language plpgsql stable security definer set search_path = public as $$
begin
  if not public.eh_equipe() then raise exception 'apenas a equipe' using errcode = '42501'; end if;
  return coalesce((select json_agg(x order by x.criado_em) from (
    select * from public.suporte where p_status = 'todos' or status = p_status order by criado_em limit 100) x), '[]'::json);
end $$;

create or replace function public.responder_suporte(p_id bigint, p_resposta text, p_fechar boolean default false)
returns json language plpgsql security definer set search_path = public as $$
declare quem text;
begin
  if not public.eh_equipe() then raise exception 'apenas a equipe' using errcode = '42501'; end if;
  select username into quem from public.perfis where id = auth.uid();
  update public.suporte set resposta = left(trim(coalesce(p_resposta, '')), 1500), respondido_por = quem,
         respondido_em = now(), status = case when p_fechar then 'fechado' else 'respondido' end
   where id = p_id;
  return json_build_object('ok', true);
end $$;
