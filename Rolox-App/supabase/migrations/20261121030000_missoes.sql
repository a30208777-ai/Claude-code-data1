-- 🎯 Missões diárias: 3 missões por dia (as mesmas para todo mundo, sorteadas pela data).
-- Cumpriu? Toca em "Resgatar" e ganha tickets. O BANCO confere se foi cumprida de verdade,
-- olhando o que já fica registrado (visitas, curtidas, chat, emblemas, recordes).

create table if not exists public.missoes_resgatadas (
  user_id uuid not null references public.perfis(id) on delete cascade,
  codigo text not null,
  dia date not null default current_date,
  resgatada_em timestamptz not null default now(),
  primary key (user_id, codigo, dia)
);
alter table public.missoes_resgatadas enable row level security;     -- sem políticas: só pelas funções

-- catálogo: codigo, emoji, título, recompensa
create or replace function public.missoes_catalogo()
returns table (codigo text, emoji text, titulo text, recompensa int) language sql immutable as $$
  values ('jogar', '🎮', 'Jogue um jogo', 5),
         ('jogar3', '🕹️', 'Jogue 3 jogos diferentes', 10),
         ('curtir', '❤️', 'Curta um jogo', 5),
         ('chat', '💬', 'Mande 3 mensagens no chat de um jogo', 5),
         ('emblema', '🏅', 'Ganhe um emblema', 10),
         ('recorde', '🏆', 'Faça um recorde em algum jogo', 10)
$$;

create or replace function public.missao_feita(p_user uuid, p_codigo text)
returns boolean language sql stable security definer set search_path = public as $$
  select case p_codigo
    when 'jogar' then exists (select 1 from public.mapas_visitas where user_id = p_user and dia = current_date)
    when 'jogar3' then (select count(*) from public.mapas_visitas where user_id = p_user and dia = current_date) >= 3
    when 'curtir' then exists (select 1 from public.mapas_curtidas where user_id = p_user and criado_em::date = current_date)
    when 'chat' then (select count(*) from public.servidores_logados where user_id = p_user and criado_em::date = current_date) >= 3
    when 'emblema' then exists (select 1 from public.emblemas where user_id = p_user and ganho_em::date = current_date)
    when 'recorde' then exists (select 1 from public.placares where user_id = p_user and atualizado_em::date = current_date)
    else false end
$$;

create or replace function public.minhas_missoes()
returns json language plpgsql stable security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  return coalesce((select json_agg(x) from (
    select c.codigo, c.emoji, c.titulo, c.recompensa,
           public.missao_feita(eu, c.codigo) as feita,
           exists (select 1 from public.missoes_resgatadas r where r.user_id = eu and r.codigo = c.codigo and r.dia = current_date) as resgatada
      from public.missoes_catalogo() c
     order by md5(c.codigo || current_date::text)
     limit 3) x), '[]'::json);
end $$;

create or replace function public.resgatar_missao(p_codigo text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  premio int;
  saldo int;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select c.recompensa into premio from (
    select * from public.missoes_catalogo() order by md5(codigo || current_date::text) limit 3) c
   where c.codigo = p_codigo;
  if premio is null then raise exception 'essa missão não é de hoje' using errcode = 'P0001'; end if;
  if not public.missao_feita(eu, p_codigo) then raise exception 'missão ainda não cumprida' using errcode = 'P0001'; end if;
  insert into public.missoes_resgatadas (user_id, codigo) values (eu, p_codigo) on conflict do nothing;
  if not found then raise exception 'você já resgatou essa missão hoje' using errcode = 'P0001'; end if;
  update public.perfis set tickets = tickets + premio where id = eu returning tickets into saldo;
  return json_build_object('ganhou', premio, 'tickets', saldo);
end $$;
