-- v0.3: curtidas e visitas nos jogos (lista "Mais jogados").
-- Contadores em mapas; quem curtiu/visitou fica em tabelas próprias (1 curtida
-- por jogador; 1 visita por jogador por dia). Tudo por RPC (security definer).

alter table public.mapas add column if not exists curtidas integer not null default 0;
alter table public.mapas add column if not exists visitas integer not null default 0;

create table if not exists public.mapas_curtidas (
  mapa_id uuid not null references public.mapas(id) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  criado_em timestamptz not null default now(),
  primary key (mapa_id, user_id)
);
alter table public.mapas_curtidas enable row level security;
create policy "curtidas: vejo as minhas" on public.mapas_curtidas for select using (user_id = auth.uid());

create table if not exists public.mapas_visitas (
  mapa_id uuid not null references public.mapas(id) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  dia date not null default current_date,
  primary key (mapa_id, user_id, dia)
);
alter table public.mapas_visitas enable row level security;

create or replace function public.curtir_mapa(p_id uuid, p_curtir boolean)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  n integer;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if not exists (select 1 from public.mapas where id = p_id and caminho_aprovado is not null) then
    raise exception 'jogo não encontrado' using errcode = 'P0001';
  end if;
  if p_curtir then
    insert into public.mapas_curtidas (mapa_id, user_id) values (p_id, eu) on conflict do nothing;
    get diagnostics n = row_count;
    if n > 0 then update public.mapas set curtidas = curtidas + 1 where id = p_id; end if;
  else
    delete from public.mapas_curtidas where mapa_id = p_id and user_id = eu;
    get diagnostics n = row_count;
    if n > 0 then update public.mapas set curtidas = greatest(0, curtidas - 1) where id = p_id; end if;
  end if;
  return json_build_object('curtidas', (select curtidas from public.mapas where id = p_id), 'curti', p_curtir);
end $$;

create or replace function public.visitar_mapa(p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  if auth.uid() is null then return; end if;
  insert into public.mapas_visitas (mapa_id, user_id) values (p_id, auth.uid()) on conflict do nothing;
  get diagnostics n = row_count;
  if n > 0 then update public.mapas set visitas = visitas + 1 where id = p_id; end if;
end $$;
