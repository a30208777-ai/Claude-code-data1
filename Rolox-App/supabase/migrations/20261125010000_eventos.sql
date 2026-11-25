-- 🎉 Eventos: link ?e=true&evento-id=... no GitHub Pages e no Render.
-- Tabela "eventos-id" com os nomes pedidos (com hífen, por isso entre aspas).
-- dia-1/hora-1 = começo, dia-2/hora-2 = fim (horário de Brasília). e = evento ligado.
create table if not exists public."eventos-id" (
  "evento-id" text primary key check (char_length("evento-id") between 8 and 80),
  "name-e"    text not null check (char_length("name-e") between 1 and 80),
  "e"         boolean not null default true,
  "dia-1"     date not null,
  "dia-2"     date not null,
  "hora-1"    time not null default '00:00',
  "hora-2"    time not null default '23:59',
  check (("dia-2" + "hora-2") > ("dia-1" + "hora-1"))
);
alter table public."eventos-id" enable row level security;   -- sem políticas: só pela função abaixo

-- Verifica um evento: existe, está ligado (e) e está dentro do período agora (Brasília).
create or replace function public.verificar_evento(p_id text)
returns json language sql stable security definer set search_path = public as $$
  select coalesce((
    select json_build_object(
      'existe', true,
      'evento-id', ev."evento-id", 'name-e', ev."name-e", 'e', ev."e",
      'dia-1', ev."dia-1", 'dia-2', ev."dia-2", 'hora-1', ev."hora-1", 'hora-2', ev."hora-2",
      'ativo', ev."e" and (now() at time zone 'America/Sao_Paulo')
                 between (ev."dia-1" + ev."hora-1") and (ev."dia-2" + ev."hora-2"))
    from public."eventos-id" ev where ev."evento-id" = left(trim(coalesce(p_id, '')), 80)
  ), json_build_object('existe', false, 'ativo', false))
$$;
