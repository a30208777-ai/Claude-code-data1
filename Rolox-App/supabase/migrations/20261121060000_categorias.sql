-- 🏷️ Categorias dos jogos: o criador (ou o dono) escolhe; a página Jogos filtra por categoria.
alter table public.mapas add column if not exists categoria text not null default 'outros'
  check (categoria in ('obby','corrida','aventura','terror','rpg','luta','simulador','quebra_cabeca','construcao','outros'));

create or replace function public.definir_categoria(p_mapa uuid, p_categoria text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if p_categoria not in ('obby','corrida','aventura','terror','rpg','luta','simulador','quebra_cabeca','construcao','outros') then
    raise exception 'categoria inválida' using errcode = 'P0001';
  end if;
  update public.mapas set categoria = p_categoria where id = p_mapa and (autor_id = eu or public.eh_dono());
  if not found then raise exception 'só o criador muda a categoria' using errcode = '42501'; end if;
  return json_build_object('categoria', p_categoria);
end $$;
