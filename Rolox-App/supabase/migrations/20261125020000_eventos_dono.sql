-- 🎉 Eventos 2: jogo do evento (quem entra vai direto nele) + o dono cria/edita eventos.
alter table public."eventos-id" add column if not exists "jogo-id" uuid references public.mapas(id) on delete set null;

create or replace function public.verificar_evento(p_id text)
returns json language sql stable security definer set search_path = public as $$
  select coalesce((
    select json_build_object(
      'existe', true,
      'evento-id', ev."evento-id", 'name-e', ev."name-e", 'e', ev."e",
      'dia-1', ev."dia-1", 'dia-2', ev."dia-2", 'hora-1', ev."hora-1", 'hora-2', ev."hora-2",
      'jogo-id', ev."jogo-id",
      'ativo', ev."e" and (now() at time zone 'America/Sao_Paulo')
                 between (ev."dia-1" + ev."hora-1") and (ev."dia-2" + ev."hora-2"))
    from public."eventos-id" ev where ev."evento-id" = left(trim(coalesce(p_id, '')), 80)
  ), json_build_object('existe', false, 'ativo', false))
$$;

create or replace function public.listar_eventos()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  return coalesce((select json_agg(x order by x."dia-1" desc, x."hora-1" desc) from (
    select ev.*, m.nome as jogo_nome from public."eventos-id" ev left join public.mapas m on m.id = ev."jogo-id") x), '[]'::json);
end $$;

-- p_id vazio = evento novo (o id é sorteado). O jogo precisa estar aprovado.
create or replace function public.salvar_evento(p_id text, p_nome text, p_e boolean, p_dia1 date, p_dia2 date,
                                                p_hora1 time, p_hora2 time, p_jogo uuid default null)
returns json language plpgsql security definer set search_path = public as $$
declare novo text := nullif(trim(coalesce(p_id, '')), '');
begin
  perform public.exigir_dono();
  if p_jogo is not null and not exists (select 1 from public.mapas where id = p_jogo and caminho_aprovado is not null) then
    raise exception 'esse jogo não está aprovado';
  end if;
  novo := coalesce(novo, replace(gen_random_uuid()::text, '-', ''));
  insert into public."eventos-id" ("evento-id", "name-e", e, "dia-1", "dia-2", "hora-1", "hora-2", "jogo-id")
  values (novo, left(trim(p_nome), 80), coalesce(p_e, true), p_dia1, p_dia2, coalesce(p_hora1, '00:00'), coalesce(p_hora2, '23:59'), p_jogo)
  on conflict ("evento-id") do update set "name-e" = excluded."name-e", e = excluded.e, "dia-1" = excluded."dia-1",
    "dia-2" = excluded."dia-2", "hora-1" = excluded."hora-1", "hora-2" = excluded."hora-2", "jogo-id" = excluded."jogo-id";
  return public.verificar_evento(novo);
end $$;
