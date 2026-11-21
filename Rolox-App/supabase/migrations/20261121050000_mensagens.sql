-- 💌 Mensagens privadas: só entre amigos (amizade aceita), com o filtro de palavras do chat.
create table if not exists public.mensagens_privadas (
  id bigint generated always as identity primary key,
  de uuid not null references public.perfis(id) on delete cascade,
  para uuid not null references public.perfis(id) on delete cascade,
  texto text not null check (char_length(texto) between 1 and 500),
  criado_em timestamptz not null default now(),
  lida boolean not null default false
);
create index if not exists mp_conversa on public.mensagens_privadas (least(de, para), greatest(de, para), id);
alter table public.mensagens_privadas enable row level security;

create or replace function public.sao_amigos(a uuid, b uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.amizades where status = 'aceita' and ((de = a and para = b) or (de = b and para = a)))
$$;

create or replace function public.enviar_mensagem_privada(p_para text, p_texto text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid; t text := left(trim(coalesce(p_texto, '')), 500); ultimas int;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_para)) and not banido;
  if alvo is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  if not public.sao_amigos(eu, alvo) then raise exception 'só dá para mandar mensagem para amigos' using errcode = 'P0001'; end if;
  if t = '' then raise exception 'mensagem vazia' using errcode = 'P0001'; end if;
  select count(*) into ultimas from public.mensagens_privadas where de = eu and criado_em > now() - interval '1 minute';
  if ultimas >= 20 then raise exception 'muitas mensagens seguidas, espere um pouco' using errcode = 'P0001'; end if;
  insert into public.mensagens_privadas (de, para, texto) values (eu, alvo, left(public.filtrar_texto(t), 500));
  return json_build_object('ok', true);
end $$;

create or replace function public.conversa_privada(p_com text, p_limite int default 50)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); outro uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into outro from public.perfis where username = lower(trim(p_com));
  if outro is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  update public.mensagens_privadas set lida = true where de = outro and para = eu and not lida;
  return coalesce((select json_agg(x order by x.id) from (
    select m.id, (m.de = eu) as minha, m.texto, m.criado_em from public.mensagens_privadas m
     where (m.de = eu and m.para = outro) or (m.de = outro and m.para = eu)
     order by m.id desc limit greatest(1, least(p_limite, 200))) x), '[]'::json);
end $$;

create or replace function public.minhas_conversas()
returns json language plpgsql stable security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  return coalesce((select json_agg(x order by x.ultima desc) from (
    select p.username, max(m.criado_em) as ultima,
           count(*) filter (where m.para = eu and not m.lida) as nao_lidas,
           (array_agg(m.texto order by m.id desc))[1] as previa
      from public.mensagens_privadas m
      join public.perfis p on p.id = case when m.de = eu then m.para else m.de end
     where m.de = eu or m.para = eu
     group by p.username) x), '[]'::json);
end $$;
