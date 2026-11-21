-- Poderes do dono no jogo (botão 👑💎 ao lado do nome do jogo):
--  * o dono usa os 2 apps normalmente: entra em servidor normal E em servidor hack de qualquer jogo
--    (a separação normal/hack não vale para ele);
--  * expulsar (kick) alguém do servidor e banir a conta, mesmo sem ser ADM.

create or replace function public.motivo_bloqueio(p_user uuid, p_server public.servidores_ativos)
returns text language sql stable set search_path = public as $$
  select case
    when p.banido then 'conta_banida'
    when exists (select 1 from public.config_servidor c where c.nome = 'dono_username' and c.valor = p.username)
      then null                                                     -- o dono entra em qualquer servidor
    when p.jogo_mod is not distinct from p_server.gameid and not p_server.is_hack_server
      then 'use_servidor_hack'
    when p_server.is_hack_server and p.jogo_mod is distinct from p_server.gameid
      then 'servidor_so_para_hack'
    else null
  end
  from public.perfis p where p.id = p_user
$$;

-- tira a pessoa do servidor (o site também a tira da sala do jogo na hora)
create or replace function public.dono_expulsar(p_server uuid, p_user uuid)
returns json language plpgsql security definer set search_path = public as $$
declare nome text;
begin
  perform public.exigir_dono();
  if p_user = auth.uid() then raise exception 'você não pode expulsar a si mesmo' using errcode = 'P0001'; end if;
  select username into nome from public.perfis where id = p_user;
  if nome is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  delete from public.users_dos_servidores where server_uid = p_server and user_id = p_user;
  delete from public.espera where server_uid = p_server and user_id = p_user;
  update public.servidores_ativos set status = 'aberto' where server_uid = p_server and status = 'cheio';
  perform public.registrar_local(p_user, 'lobby', null);
  return json_build_object('username', nome);
end $$;

create or replace function public.dono_banir(p_user uuid, p_motivo text default null)
returns json language plpgsql security definer set search_path = public as $$
declare nome text;
begin
  perform public.exigir_dono();
  if p_user = auth.uid() then raise exception 'você não pode banir a si mesmo' using errcode = 'P0001'; end if;
  update public.perfis set banido = true, motivo_ban = left(coalesce(nullif(trim(p_motivo), ''), 'banido pelo dono'), 200)
   where id = p_user returning username into nome;
  if nome is null then raise exception 'jogador não encontrado' using errcode = 'P0001'; end if;
  delete from public.users_dos_servidores where user_id = p_user;
  delete from public.espera where user_id = p_user;
  return json_build_object('username', nome);
end $$;

-- O DONO NUNCA PODE SER BANIDO (nem por ADM, nem por função nenhuma, nem direto no banco).
create or replace function public.eh_conta_dono(p_username text)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.config_servidor c where c.nome = 'dono_username' and c.valor = p_username)
$$;

create or replace function public.dono_nao_pode_ser_banido()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.banido and not coalesce(old.banido, false) and public.eh_conta_dono(new.username) then
    raise exception 'o dono do ROLOX não pode ser banido' using errcode = '42501';
  end if;
  return new;
end $$;

create trigger dono_nao_pode_ser_banido
  before update of banido on public.perfis
  for each row execute function public.dono_nao_pode_ser_banido();
