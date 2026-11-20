-- v0.15: denúncias de jogador e de jogo, com fila de moderação (ADM ou dono).
create table if not exists public.denuncias (
  id bigint generated always as identity primary key,
  de uuid not null references public.perfis(id) on delete cascade,
  tipo text not null check (tipo in ('jogador', 'jogo')),
  alvo text not null check (char_length(alvo) between 1 and 64),
  alvo_nome text not null default '',
  motivo text not null check (motivo in ('xingamento', 'trapaca', 'golpe', 'improprio', 'spam', 'outro')),
  detalhe text not null default '' check (char_length(detalhe) <= 300),
  status text not null default 'aberta' check (status in ('aberta', 'resolvida', 'descartada')),
  nota text,
  resolvido_por uuid references public.perfis(id) on delete set null,
  criado_em timestamptz not null default now(),
  resolvido_em timestamptz
);
create index if not exists denuncias_abertas on public.denuncias (status, criado_em);
alter table public.denuncias enable row level security;     -- sem políticas: só pelas funções

create or replace function public.denunciar(p_tipo text, p_alvo text, p_motivo text, p_detalhe text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  nome text;
  novo bigint;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if (select count(*) from public.denuncias where de = eu and criado_em > now() - interval '1 day') >= 10 then
    raise exception 'você já fez 10 denúncias hoje; a moderação vai olhar' using errcode = 'P0001';
  end if;
  if p_tipo = 'jogador' then
    select username into nome from public.perfis where username = lower(trim(p_alvo));
    if nome is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
    if exists (select 1 from public.perfis where id = eu and username = nome) then
      raise exception 'você não pode se denunciar' using errcode = 'P0001';
    end if;
  elsif p_tipo = 'jogo' then
    select m.nome into nome from public.mapas m where m.id::text = trim(p_alvo) and m.caminho_aprovado is not null;
    if nome is null then raise exception 'jogo não encontrado' using errcode = 'P0001'; end if;
  else
    raise exception 'tipo inválido' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.denuncias where de = eu and tipo = p_tipo and alvo = lower(trim(p_alvo)) and status = 'aberta') then
    return json_build_object('ok', true, 'repetida', true, 'alvo_nome', nome);
  end if;
  insert into public.denuncias (de, tipo, alvo, alvo_nome, motivo, detalhe)
  values (eu, p_tipo, lower(trim(p_alvo)), nome, p_motivo, left(coalesce(trim(p_detalhe), ''), 300))
  returning id into novo;
  return json_build_object('ok', true, 'id', novo, 'alvo_nome', nome);
end $$;

create or replace function public.adm_denuncias(p_status text default 'aberta')
returns json language plpgsql stable security definer set search_path = public as $$
begin
  if not (public.eh_adm() or public.eh_dono()) then raise exception 'apenas ADM' using errcode = '42501'; end if;
  return coalesce((select json_agg(x order by x.criado_em desc) from (
    select d.id, d.tipo, d.alvo, d.alvo_nome, d.motivo, d.detalhe, d.status, d.nota, d.criado_em,
           p.username as denunciante,
           (select count(*) from public.denuncias o where o.tipo = d.tipo and o.alvo = d.alvo and o.status = 'aberta') as vezes
      from public.denuncias d join public.perfis p on p.id = d.de
     where d.status = coalesce(p_status, 'aberta')
     limit 200) x), '[]'::json);
end $$;

create or replace function public.adm_resolver_denuncia(p_id bigint, p_status text, p_nota text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not (public.eh_adm() or public.eh_dono()) then raise exception 'apenas ADM' using errcode = '42501'; end if;
  if p_status not in ('resolvida', 'descartada') then raise exception 'status inválido' using errcode = 'P0001'; end if;
  update public.denuncias set status = p_status, nota = left(coalesce(trim(p_nota), ''), 300),
         resolvido_por = auth.uid(), resolvido_em = now()
   where id = p_id and status = 'aberta';
end $$;
