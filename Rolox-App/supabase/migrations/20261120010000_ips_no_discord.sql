-- IPs bloqueados automaticamente (3 senhas erradas) também vão para o webhook de
-- banimentos: o painel ADM registra os que faltam e marca aqui (não repete entre ADMs).

alter table public.ips_bloqueados add column registrado_discord boolean not null default false;

create function public.adm_marcar_ip_registrado(p_ip text)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_adm();
  update public.ips_bloqueados set registrado_discord = true where ip = p_ip::inet;
end $$;

create or replace function public.adm_painel()
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
        select id, username, tickets, is_adm, banido, motivo_ban, criado_em,
               case when sem_chat_ate > now() then sem_chat_ate end as sem_chat_ate,
               case when sem_chat_ate > now() then sem_chat_motivo end as sem_chat_motivo
          from public.perfis order by criado_em desc limit 200) u), '[]'::json),
    'ips_bloqueados', coalesce((select json_agg(i) from (
        select b.ip::text as ip, p.username as conta_alvo, b.motivo, b.bloqueado_em, b.registrado_discord,
               (b.bloqueado_por is null) as automatico
          from public.ips_bloqueados b left join public.perfis p on p.id = b.conta_alvo
         order by b.bloqueado_em desc limit 200) i), '[]'::json),
    'servidores', coalesce((select json_agg(s) from (
        select s.server_uid, s.gameid, s.capacidade, s.is_hack_server, s.criado_em,
               (select count(*) from public.users_dos_servidores u where u.server_uid = s.server_uid) as humanos,
               (select count(*) from public.bots_dos_servidores b where b.server_uid = s.server_uid) as ias
          from public.servidores_ativos s order by s.criado_em desc limit 200) s), '[]'::json)
  );
end $$;
