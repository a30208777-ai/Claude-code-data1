-- 👥 Seguir e seguidores: qualquer jogador pode seguir outro (não precisa ser amigo).
create table if not exists public.seguidores (
  seguidor uuid not null references public.perfis(id) on delete cascade,
  seguido uuid not null references public.perfis(id) on delete cascade,
  criado_em timestamptz not null default now(),
  primary key (seguidor, seguido),
  check (seguidor <> seguido)
);
create index if not exists seguidores_seguido on public.seguidores (seguido);
alter table public.seguidores enable row level security;

create or replace function public.seguir(p_nome text, p_seguir boolean default true)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_nome)) and not banido;
  if alvo is null then raise exception 'jogador não encontrado'; end if;
  if alvo = eu then raise exception 'você não pode seguir você mesmo'; end if;
  if p_seguir then
    if (select count(*) from public.seguidores where seguidor = eu) >= 2000 then raise exception 'limite de 2000 seguindo'; end if;
    insert into public.seguidores (seguidor, seguido) values (eu, alvo) on conflict do nothing;
  else
    delete from public.seguidores where seguidor = eu and seguido = alvo;
  end if;
  return json_build_object('seguindo', p_seguir);
end $$;

create or replace function public.info_seguidores(p_nome text)
returns json language plpgsql stable security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_nome));
  if alvo is null then return null; end if;
  return json_build_object(
    'seguidores', (select count(*) from public.seguidores where seguido = alvo),
    'seguindo', (select count(*) from public.seguidores where seguidor = alvo),
    'eu_sigo', exists (select 1 from public.seguidores where seguidor = eu and seguido = alvo));
end $$;

create or replace function public.lista_seguidores(p_nome text, p_tipo text default 'seguidores')
returns json language plpgsql stable security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_nome));
  if alvo is null then return '[]'::json; end if;
  return coalesce((select json_agg(x) from (
    select p.username, s.criado_em from public.seguidores s
      join public.perfis p on p.id = case when p_tipo = 'seguindo' then s.seguido else s.seguidor end
     where (case when p_tipo = 'seguindo' then s.seguidor else s.seguido end) = alvo and not p.banido
     order by s.criado_em desc limit 200) x), '[]'::json);
end $$;
