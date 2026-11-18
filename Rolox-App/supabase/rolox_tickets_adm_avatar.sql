alter table public.perfis rename column is_admin to is_adm;

alter table public.perfis
  add column tickets bigint not null default 0 check (tickets >= 0),
  add column tickets_ultimo_ganho int not null default 0,
  add column tickets_ultimo_dia date,
  add column avatar jsonb not null default '{}'::jsonb
    check (jsonb_typeof(avatar) = 'object' and pg_column_size(avatar) < 2000);

update public.perfis set is_adm = true where username = 'admtest';

create table public.historico_tickets (
  id         bigserial primary key,
  user_id    uuid not null references public.perfis(id) on delete cascade,
  delta      bigint not null,
  motivo     text not null,
  criado_em  timestamptz not null default now()
);
create index historico_tickets_user on public.historico_tickets (user_id, criado_em desc);
alter table public.historico_tickets enable row level security;
create policy "dono vê o próprio histórico" on public.historico_tickets
  for select to authenticated using (auth.uid() = user_id);

create function public.proteger_perfil()
returns trigger language plpgsql as $$
begin
  if current_user in ('authenticated', 'anon') and (
       new.id is distinct from old.id
    or new.username is distinct from old.username
    or new.is_adm is distinct from old.is_adm
    or new.banido is distinct from old.banido
    or new.motivo_ban is distinct from old.motivo_ban
    or new.tickets is distinct from old.tickets
    or new.tickets_ultimo_ganho is distinct from old.tickets_ultimo_ganho
    or new.tickets_ultimo_dia is distinct from old.tickets_ultimo_dia) then
    raise exception 'campo protegido do perfil' using errcode = '42501';
  end if;
  return new;
end $$;

create trigger proteger_perfil
  before update on public.perfis
  for each row execute function public.proteger_perfil();

create function public.eh_adm()
returns boolean language sql stable security definer set search_path = public as $$
  select coalesce((select is_adm from public.perfis where id = auth.uid()), false)
$$;

create function public.receber_tickets_diarios()
returns json language plpgsql security definer set search_path = public as $$
declare
  uid uuid := auth.uid();
  p public.perfis;
  hoje date := (now() at time zone 'America/Sao_Paulo')::date;
  ganho int;
begin
  if uid is null then raise exception 'não autenticado'; end if;
  select * into p from public.perfis where id = uid for update;
  if not found then raise exception 'perfil não encontrado'; end if;

  if p.is_adm then
    return json_build_object('infinito', true, 'ganhou', 0);
  end if;

  if p.tickets_ultimo_dia = hoje then
    return json_build_object('infinito', false, 'ganhou', 0, 'tickets', p.tickets,
      'amanha', least(greatest(p.tickets_ultimo_ganho, 5) * 2, 640));
  end if;

  ganho := case when p.tickets_ultimo_ganho <= 0 then 5
                else least(p.tickets_ultimo_ganho * 2, 640) end;

  update public.perfis
     set tickets = tickets + ganho, tickets_ultimo_ganho = ganho, tickets_ultimo_dia = hoje
   where id = uid;
  insert into public.historico_tickets (user_id, delta, motivo) values (uid, ganho, 'presente diário');

  return json_build_object('infinito', false, 'ganhou', ganho, 'tickets', p.tickets + ganho,
    'amanha', least(ganho * 2, 640));
end $$;

create function public.gastar_ticket(p_user uuid)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'só o servidor pode gastar tickets' using errcode = '42501';
  end if;
  if exists (select 1 from public.perfis where id = p_user and is_adm) then
    return true;
  end if;
  update public.perfis set tickets = tickets - 1 where id = p_user and tickets > 0;
  if not found then return false; end if;
  insert into public.historico_tickets (user_id, delta, motivo) values (p_user, -1, 'resposta de IA');
  return true;
end $$;

create function public.devolver_ticket(p_user uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'só o servidor pode devolver tickets' using errcode = '42501';
  end if;
  if exists (select 1 from public.perfis where id = p_user and is_adm) then return; end if;
  update public.perfis set tickets = tickets + 1 where id = p_user;
  insert into public.historico_tickets (user_id, delta, motivo) values (p_user, 1, 'IA não respondeu (devolvido)');
end $$;

create function public.exigir_adm()
returns void language plpgsql stable security definer set search_path = public as $$
begin
  if not public.eh_adm() then
    raise exception 'apenas ADM' using errcode = '42501';
  end if;
end $$;

create function public.adm_painel()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  return json_build_object(
    'totais', json_build_object(
      'usuarios', (select count(*) from public.perfis),
      'servidores', (select count(*) from public.servidores_ativos),
      'ips_bloqueados', (select count(*) from public.ips_bloqueados),
      'alertas_hoje', (select count(*) from public.alertas_seguranca where criado_em > now() - interval '1 day')),
    'usuarios', coalesce((select json_agg(u) from (
        select id, username, tickets, is_adm, banido, motivo_ban, criado_em
          from public.perfis order by criado_em desc limit 200) u), '[]'::json),
    'ips_bloqueados', coalesce((select json_agg(i) from (
        select b.ip::text as ip, p.username as conta_alvo, b.motivo, b.bloqueado_em
          from public.ips_bloqueados b left join public.perfis p on p.id = b.conta_alvo
         order by b.bloqueado_em desc limit 200) i), '[]'::json),
    'servidores', coalesce((select json_agg(s) from (
        select s.server_uid, s.gameid, s.capacidade, s.is_hack_server, s.criado_em,
               (select count(*) from public.users_dos_servidores u where u.server_uid = s.server_uid) as humanos,
               (select count(*) from public.bots_dos_servidores b where b.server_uid = s.server_uid) as ias
          from public.servidores_ativos s order by s.criado_em desc limit 200) s), '[]'::json)
  );
end $$;

create function public.adm_dar_tickets(p_user uuid, p_qtd int)
returns json language plpgsql security definer set search_path = public as $$
declare novo bigint;
begin
  perform public.exigir_adm();
  if p_qtd is null or p_qtd = 0 or abs(p_qtd) > 1000000 then
    raise exception 'quantidade inválida';
  end if;
  update public.perfis set tickets = greatest(0, tickets + p_qtd) where id = p_user returning tickets into novo;
  if not found then raise exception 'usuário não encontrado'; end if;
  insert into public.historico_tickets (user_id, delta, motivo) values (p_user, p_qtd, 'ajuste de ADM');
  return json_build_object('tickets', novo);
end $$;

create function public.adm_banir(p_user uuid, p_motivo text default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  if p_user = auth.uid() then raise exception 'você não pode banir a si mesmo'; end if;
  update public.perfis set banido = true, motivo_ban = left(coalesce(p_motivo, 'banido por ADM'), 200)
   where id = p_user;
  delete from public.users_dos_servidores where user_id = p_user;
  delete from public.espera where user_id = p_user;
end $$;

create function public.adm_desbanir(p_user uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  update public.perfis set banido = false, motivo_ban = null where id = p_user;
end $$;

create function public.adm_desbloquear_ip(p_ip text)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  delete from public.ips_bloqueados where ip = p_ip::inet;
  delete from public.tentativas_login where ip = p_ip::inet;
end $$;

create function public.adm_encerrar_servidor(p_server uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  delete from public.servidores_ativos where server_uid = p_server;
end $$;

create function public.adm_definir_adm(p_user uuid, p_adm boolean)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  if p_user = auth.uid() and not p_adm then raise exception 'você não pode tirar o próprio ADM'; end if;
  update public.perfis set is_adm = p_adm where id = p_user;
end $$;
