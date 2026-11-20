-- v0.5: amigos. Pedido -> aceitar/recusar -> amigos. Onde o amigo está jogando só
-- aparece se ele marcou "Mostrar para amigos onde estou jogando" (aceitou_localizacao).
create table if not exists public.amizades (
  de uuid not null references public.perfis(id) on delete cascade,
  para uuid not null references public.perfis(id) on delete cascade,
  status text not null default 'pendente' check (status in ('pendente', 'aceita')),
  criado_em timestamptz not null default now(),
  primary key (de, para),
  check (de <> para)
);
create index if not exists amizades_para on public.amizades (para);
alter table public.amizades enable row level security;
create policy "amizades: as minhas" on public.amizades for select using (de = auth.uid() or para = auth.uid());

create or replace function public.pedir_amizade(p_username text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  outro uuid;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select id into outro from public.perfis where username = lower(trim(p_username)) and not banido;
  if outro is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  if outro = eu then raise exception 'você não pode se adicionar' using errcode = 'P0001'; end if;
  if (select count(*) from public.amizades where de = eu and status = 'pendente') >= 50 then
    raise exception 'muitos pedidos pendentes' using errcode = 'P0001';
  end if;
  -- ele já tinha me pedido? então vira amizade
  update public.amizades set status = 'aceita' where de = outro and para = eu;
  if found then return json_build_object('status', 'aceita'); end if;
  insert into public.amizades (de, para) values (eu, outro) on conflict do nothing;
  return json_build_object('status', coalesce((select status from public.amizades where de = eu and para = outro), 'pendente'));
end $$;

create or replace function public.responder_amizade(p_de uuid, p_aceitar boolean)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_aceitar then
    update public.amizades set status = 'aceita' where de = p_de and para = auth.uid() and status = 'pendente';
  else
    delete from public.amizades where de = p_de and para = auth.uid() and status = 'pendente';
  end if;
end $$;

create or replace function public.desfazer_amizade(p_outro uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  delete from public.amizades where (de = auth.uid() and para = p_outro) or (de = p_outro and para = auth.uid());
end $$;

-- Lista: amigos (com status online/jogando, se ele permitir), pedidos recebidos e enviados.
create or replace function public.meus_amigos()
returns json language sql stable security definer set search_path = public as $$
  with minhas as (
    select case when a.de = auth.uid() then a.para else a.de end as outro, a.status,
           case when a.status = 'aceita' then 'amigo' when a.para = auth.uid() then 'recebido' else 'enviado' end as tipo
      from public.amizades a where a.de = auth.uid() or a.para = auth.uid()
  )
  select coalesce(json_agg(json_build_object(
    'id', p.id, 'username', p.username, 'tipo', m.tipo, 'avatar', p.avatar,
    'online', m.tipo = 'amigo' and (u.server_uid is not null or l.atualizado_em > now() - interval '10 minutes'),
    'server_uid', case when m.tipo = 'amigo' and p.aceitou_localizacao then u.server_uid end,
    'gameid', case when m.tipo = 'amigo' and p.aceitou_localizacao then s.gameid end,
    'jogo', case when m.tipo = 'amigo' and p.aceitou_localizacao then j.nome end,
    'mapa_id', case when m.tipo = 'amigo' and p.aceitou_localizacao then mp.id end
  ) order by (u.server_uid is not null) desc, p.username), '[]'::json)
  from minhas m
  join public.perfis p on p.id = m.outro
  left join public.users_dos_servidores u on u.user_id = p.id
  left join public.servidores_ativos s on s.server_uid = u.server_uid
  left join public.jogos j on j.gameid = s.gameid
  left join public.mapas mp on mp.gameid = s.gameid
  left join public.locate_users l on l.user_id = p.id
  where auth.uid() is not null
$$;
