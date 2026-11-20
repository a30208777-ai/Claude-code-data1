-- IA do ROLOX Studio (site): cada mensagem custa 10 tickets.
-- Gastar: o próprio jogador (só mexe nos tickets dele). ADM = infinito.
-- Devolver (quando nenhuma IA respondeu): só o servidor do site, com a chave
-- do proxy (config_servidor 'proxy_chave'), 1 vez por cobrança, até 5 min depois.
create or replace function public.gastar_tickets_studio_ia()
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  restante bigint;
  cobranca bigint;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if exists (select 1 from public.perfis where id = eu and is_adm) then
    return json_build_object('infinito', true, 'tickets', null, 'cobranca', null);
  end if;
  update public.perfis set tickets = tickets - 10 where id = eu and tickets >= 10 and not banido
  returning tickets into restante;
  if not found then
    raise exception 'tickets insuficientes: cada mensagem da IA do Studio custa 10 tickets' using errcode = 'P0001';
  end if;
  insert into public.historico_tickets (user_id, delta, motivo) values (eu, -10, 'IA do Studio')
  returning id into cobranca;
  return json_build_object('infinito', false, 'tickets', restante, 'cobranca', cobranca);
end $$;

create or replace function public.devolver_tickets_studio_ia(p_cobranca bigint, p_chave text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  restante bigint;
begin
  if p_chave is null or p_chave is distinct from (select valor from public.config_servidor where nome = 'proxy_chave') then
    raise exception 'só o servidor do site pode devolver' using errcode = '42501';
  end if;
  update public.historico_tickets set motivo = 'IA do Studio (devolvido)'
   where id = p_cobranca and user_id = eu and motivo = 'IA do Studio' and delta = -10
     and criado_em > now() - interval '5 minutes';
  if not found then return json_build_object('devolvido', false); end if;
  update public.perfis set tickets = tickets + 10 where id = eu returning tickets into restante;
  insert into public.historico_tickets (user_id, delta, motivo) values (eu, 10, 'IA do Studio não respondeu (devolvido)');
  return json_build_object('devolvido', true, 'tickets', restante);
end $$;
