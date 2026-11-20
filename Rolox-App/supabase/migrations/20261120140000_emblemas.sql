-- v0.17: Emblemas — cada jogo dá emblemas pelos scripts; ficam na página do jogador.
create table if not exists public.emblemas (
  mapa_id uuid not null references public.mapas(id) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  codigo text not null check (codigo ~ '^[A-Za-z0-9_]{1,30}$'),
  nome text not null check (char_length(nome) between 1 and 40),
  emoji text not null default '🏅' check (char_length(emoji) between 1 and 8),
  ganho_em timestamptz not null default now(),
  primary key (mapa_id, user_id, codigo)
);
alter table public.emblemas enable row level security;      -- sem políticas: só pelas funções

create or replace function public.dar_emblema(p_mapa uuid, p_codigo text, p_nome text, p_emoji text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  n int;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if not exists (select 1 from public.mapas where id = p_mapa and caminho_aprovado is not null) then
    raise exception 'jogo não encontrado' using errcode = 'P0001';
  end if;
  if coalesce(p_codigo, '') !~ '^[A-Za-z0-9_]{1,30}$' then raise exception 'código de emblema inválido' using errcode = 'P0001'; end if;
  if (select count(*) from public.emblemas where mapa_id = p_mapa and user_id = eu) >= 30 then
    return json_build_object('novo', false, 'limite', true);
  end if;
  insert into public.emblemas (mapa_id, user_id, codigo, nome, emoji)
  values (p_mapa, eu, p_codigo, left(coalesce(nullif(trim(p_nome), ''), p_codigo), 40),
          coalesce(nullif(left(trim(p_emoji), 8), ''), '🏅'))
  on conflict do nothing;
  get diagnostics n = row_count;
  return json_build_object('novo', n > 0);
end $$;

create or replace function public.meus_emblemas(p_mapa uuid)
returns json language sql stable security definer set search_path = public as $$
  select coalesce(json_agg(codigo), '[]'::json) from public.emblemas where mapa_id = p_mapa and user_id = auth.uid()
$$;

create or replace function public.emblemas_de(p_username text)
returns json language sql stable security definer set search_path = public as $$
  select coalesce(json_agg(json_build_object('jogo', m.nome, 'mapa_id', m.id, 'codigo', e.codigo, 'nome', e.nome,
                                             'emoji', e.emoji, 'ganho_em', e.ganho_em) order by e.ganho_em desc), '[]'::json)
    from public.emblemas e join public.perfis p on p.id = e.user_id join public.mapas m on m.id = e.mapa_id
   where p.username = lower(trim(p_username)) and auth.uid() is not null
$$;
