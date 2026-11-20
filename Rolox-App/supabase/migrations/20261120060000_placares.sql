-- v0.4: placar (recorde) por jogo. O jogo manda o 1º valor de leaderstats do jogador;
-- fica o MAIOR de cada um. Ranking público para quem está logado.
create table if not exists public.placares (
  mapa_id uuid not null references public.mapas(id) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  username text not null,
  estatistica text not null check (char_length(estatistica) between 1 and 32),
  valor numeric not null,
  atualizado_em timestamptz not null default now(),
  primary key (mapa_id, user_id)
);
create index if not exists placares_ranking on public.placares (mapa_id, valor desc);
alter table public.placares enable row level security;
create policy "placares: logados veem" on public.placares for select to authenticated using (true);

create or replace function public.registrar_placar(p_id uuid, p_estatistica text, p_valor numeric)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  nome text;
  melhor numeric;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if p_valor is null or p_valor < 0 or p_valor > 1e12 then raise exception 'valor inválido' using errcode = 'P0001'; end if;
  if not exists (select 1 from public.mapas where id = p_id and caminho_aprovado is not null) then
    raise exception 'jogo não encontrado' using errcode = 'P0001';
  end if;
  select username into nome from public.perfis where id = eu and not banido;
  if nome is null then raise exception 'conta indisponível' using errcode = '42501'; end if;
  insert into public.placares (mapa_id, user_id, username, estatistica, valor)
  values (p_id, eu, nome, left(coalesce(nullif(trim(p_estatistica), ''), 'Pontos'), 32), p_valor)
  on conflict (mapa_id, user_id) do update
     set valor = greatest(placares.valor, excluded.valor), estatistica = excluded.estatistica,
         username = excluded.username,
         atualizado_em = case when excluded.valor > placares.valor then now() else placares.atualizado_em end
  returning valor into melhor;
  return json_build_object('recorde', melhor);
end $$;
