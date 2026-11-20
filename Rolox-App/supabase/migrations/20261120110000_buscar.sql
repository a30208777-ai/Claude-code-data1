-- Busca de jogadores e jogos com ORDEM DE RELEVÂNCIA (não "todo mundo que contém a palavra"):
--   0 = igual ao termo, 1 = começa com o termo, 2 = uma palavra começa com o termo, 3 = contém.
-- Dentro de cada nível: nomes mais curtos (mais parecidos) primeiro. Limite de resultados.
create or replace function public.buscar_jogadores(p_termo text, p_limite int default 20)
returns json language plpgsql stable security definer set search_path = public as $$
declare
  t text := lower(trim(coalesce(p_termo, '')));
  esc text;
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if char_length(t) < 2 or char_length(t) > 32 then return '[]'::json; end if;
  esc := replace(replace(replace(t, '\', '\\'), '%', '\%'), '_', '\_');
  return coalesce((select json_agg(x) from (
    select p.username, p.avatar, p.is_parceiro,
           case when p.username = t then 0
                when p.username like esc || '%' then 1
                when p.username ~ ('[._-]' || regexp_replace(t, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g')) then 2
                else 3 end as nivel
      from public.perfis p
     where not p.banido and p.username like '%' || esc || '%'
     order by nivel, char_length(p.username), p.username
     limit greatest(1, least(p_limite, 50))) x), '[]'::json);
end $$;

create or replace function public.buscar_jogos(p_termo text, p_limite int default 20)
returns json language plpgsql stable security definer set search_path = public as $$
declare
  t text := lower(trim(coalesce(p_termo, '')));
  esc text;
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if char_length(t) < 2 or char_length(t) > 40 then return '[]'::json; end if;
  esc := replace(replace(replace(t, '\', '\\'), '%', '\%'), '_', '\_');
  return coalesce((select json_agg(x) from (
    select m.id, m.nome, m.descricao, m.curtidas, m.visitas,
           case when lower(m.nome) = t then 0
                when lower(m.nome) like esc || '%' then 1
                when lower(m.nome) like '% ' || esc || '%' or lower(m.nome) like '%-' || esc || '%' then 2
                when lower(m.nome) like '%' || esc || '%' then 3
                else 4 end as nivel
      from public.mapas m
     where m.caminho_aprovado is not null
       and (lower(m.nome) like '%' || esc || '%' or lower(m.descricao) like '%' || esc || '%')
     order by nivel, m.visitas desc, char_length(m.nome), m.nome
     limit greatest(1, least(p_limite, 50))) x), '[]'::json);
end $$;
