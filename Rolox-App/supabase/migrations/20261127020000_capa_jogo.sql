-- 🖼️ Capa do jogo (como o ícone dos jogos do ROBLOX): o criador escolhe um ícone e uma cor.
alter table public.mapas add column if not exists icone text not null default '🕹️' check (char_length(icone) between 1 and 8);
alter table public.mapas add column if not exists cor_capa text not null default '#5e35b1' check (cor_capa ~ '^#[0-9a-fA-F]{6}$');

create or replace function public.definir_capa(p_mapa uuid, p_icone text, p_cor text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if p_cor !~ '^#[0-9a-fA-F]{6}$' or char_length(coalesce(p_icone, '')) not between 1 and 8 then
    raise exception 'capa inválida' using errcode = 'P0001';
  end if;
  update public.mapas set icone = p_icone, cor_capa = lower(p_cor) where id = p_mapa and (autor_id = eu or public.eh_dono());
  if not found then raise exception 'só o criador muda a capa' using errcode = '42501'; end if;
  return json_build_object('icone', p_icone, 'cor', lower(p_cor));
end $$;
