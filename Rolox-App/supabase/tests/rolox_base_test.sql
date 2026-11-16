\set ON_ERROR_STOP 1
insert into auth.users (id, email, raw_user_meta_data) values
 ('00000000-0000-0000-0000-00000000000a','a@x','{"username":"Alice","aceitou_localizacao":true}'),
 ('00000000-0000-0000-0000-00000000000b','b@x','{"username":"bob"}'),
 ('00000000-0000-0000-0000-00000000000c','c@x','{"username":"carol"}'),
 ('00000000-0000-0000-0000-00000000000d','d@x','{"username":"hacker1"}');
select id, username, aceitou_localizacao from perfis order by username;
insert into jogos (gameid, nome, repo, commit_aprovado) values ('corrida','Corrida','x/y','abc'), ('pendente','P','x/z',null);
update perfis set jogo_mod='corrida' where username='hacker1';
-- servidor limpo cap 2 e servidor hack
insert into servidores_ativos (server_uid, gameid, host_id, capacidade) values ('10000000-0000-0000-0000-000000000001','corrida','00000000-0000-0000-0000-00000000000a',2);
insert into servidores_ativos (server_uid, gameid, host_id, capacidade, is_hack_server) values ('10000000-0000-0000-0000-000000000002','corrida','00000000-0000-0000-0000-00000000000d',5,true);

set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000a',false);
select 'anon jogos' t, count(*) from jogos;
select entrar_servidor('10000000-0000-0000-0000-000000000001') a1;
select entrar_servidor('10000000-0000-0000-0000-000000000001') a1_dup;
select entrar_servidor('10000000-0000-0000-0000-000000000002') a_no_hack;
select enviar_mensagem('10000000-0000-0000-0000-000000000001','hj eu achei um cão mais era a porra de uma sacola') msg;
select enviar_mensagem('10000000-0000-0000-0000-000000000001','de novo') spam;
-- tentar virar admin
do $$ begin update perfis set is_admin=true where id=auth.uid(); raise notice 'FALHA: virou admin'; exception when insufficient_privilege then raise notice 'ok: admin bloqueado'; end $$;
update perfis set idioma='en' where id=auth.uid();
do $$ begin perform registrar_local(auth.uid(),'menu',null); raise notice 'FALHA registrar_local'; exception when insufficient_privilege then raise notice 'ok: registrar_local bloqueado'; end $$;
do $$ begin insert into users_dos_servidores values ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-00000000000c'); raise notice 'FALHA insert direto'; exception when insufficient_privilege then raise notice 'ok: insert direto bloqueado'; end $$;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000b',false);
select entrar_servidor('10000000-0000-0000-0000-000000000001') b1;
select count(*) as b_le_chat from servidores_logados;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000c',false);
select entrar_servidor('10000000-0000-0000-0000-000000000001') c_fila;
select count(*) as c_le_chat_fila from servidores_logados;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000d',false);
select entrar_servidor('10000000-0000-0000-0000-000000000001') hacker_limpo;
select entrar_servidor('10000000-0000-0000-0000-000000000002') hacker_hack;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000a',false);
select sair_servidor('10000000-0000-0000-0000-000000000001') a_sai;
reset role;
select p.username, u.server_uid from users_dos_servidores u join perfis p on p.id=u.user_id order by 1;
select count(*) fila from espera;
select status from servidores_ativos where server_uid='10000000-0000-0000-0000-000000000001';
select user_id, locate from locate_users;
select mensagem_filtrada from servidores_logados;
select filtrar_texto('vsf seu fdp, bora jogar') f;
update servidores_ativos set ultimo_heartbeat = now() - interval '2 minutes' where is_hack_server;
select limpar_servidores_inativos() removidos;
-- Fase 10: bob marca hack em corrida estando no servidor limpo -> é removido
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000b',false);
update perfis set jogo_mod='corrida' where id=auth.uid();
reset role;
select 'bob ainda no servidor limpo?' t, exists(select 1 from users_dos_servidores u join perfis p on p.id=u.user_id where p.username='bob') ;
