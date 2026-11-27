-- 🚫 Bloquear jogador (como no ROBLOX): quem bloqueia não recebe mensagem privada dessa pessoa (nem manda).
-- Não bloqueia a equipe (dono/ADM continuam podendo falar com você).
create table if not exists public.bloqueios (
  quem uuid not null references public.perfis(id) on delete cascade,
  bloqueado uuid not null references public.perfis(id) on delete cascade,
  criado_em timestamptz not null default now(),
  primary key (quem, bloqueado),
  check (quem <> bloqueado)
);
alter table public.bloqueios enable row level security;

create or replace function public.bloquear(p_nome text, p_sim boolean default true)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_nome));
  if alvo is null then raise exception 'jogador não encontrado'; end if;
  if alvo = eu then raise exception 'você não pode bloquear você mesmo'; end if;
  if p_sim then
    if (select count(*) from public.bloqueios where quem = eu) >= 500 then raise exception 'limite de 500 bloqueados'; end if;
    insert into public.bloqueios (quem, bloqueado) values (eu, alvo) on conflict do nothing;
  else
    delete from public.bloqueios where quem = eu and bloqueado = alvo;
  end if;
  return json_build_object('bloqueado', p_sim);
end $$;

create or replace function public.meus_bloqueados()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  return coalesce((select json_agg(p.username order by p.username) from public.bloqueios b
                     join public.perfis p on p.id = b.bloqueado where b.quem = auth.uid()), '[]'::json);
end $$;

create or replace function public.ha_bloqueio(a uuid, b uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.bloqueios where (quem = a and bloqueado = b) or (quem = b and bloqueado = a))
$$;

create or replace function public.enviar_mensagem_privada(p_para text, p_texto text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid(); alvo uuid; t text := left(trim(coalesce(p_texto, '')), 500); ultimas int;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into alvo from public.perfis where username = lower(trim(p_para)) and not banido;
  if alvo is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  if not public.sao_amigos(eu, alvo) then raise exception 'só dá para mandar mensagem para amigos' using errcode = 'P0001'; end if;
  if public.ha_bloqueio(eu, alvo) then raise exception 'não dá para mandar mensagem: há um bloqueio entre vocês' using errcode = 'P0001'; end if;
  if t = '' then raise exception 'mensagem vazia' using errcode = 'P0001'; end if;
  select count(*) into ultimas from public.mensagens_privadas where de = eu and criado_em > now() - interval '1 minute';
  if ultimas >= 20 then raise exception 'muitas mensagens seguidas, espere um pouco' using errcode = 'P0001'; end if;
  insert into public.mensagens_privadas (de, para, texto) values (eu, alvo, left(public.filtrar_texto(t), 500));
  return json_build_object('ok', true);
end $$;
