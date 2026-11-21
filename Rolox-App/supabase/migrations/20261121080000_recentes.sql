-- 🕘 Jogados recentemente (a partir das visitas de cada dia)
create or replace function public.meus_recentes(p_limite int default 6)
returns json language plpgsql stable security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  return coalesce((select json_agg(x) from (
    select m.id, m.nome, max(v.dia) as dia
      from public.mapas_visitas v join public.mapas m on m.id = v.mapa_id
     where v.user_id = eu and m.caminho_aprovado is not null
     group by m.id, m.nome
     order by max(v.dia) desc, m.nome
     limit greatest(1, least(p_limite, 20))) x), '[]'::json);
end $$;
