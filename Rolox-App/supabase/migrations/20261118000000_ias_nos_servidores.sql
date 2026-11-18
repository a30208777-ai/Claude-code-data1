-- IAs nos servidores: metade da capacidade, arredondada para baixo.
-- capacidade 10 -> 5 IAs; 11 -> 5; 3 -> 1; 1 -> 0.
-- Jogadores reais têm prioridade: se lotar, uma IA sai para abrir vaga
-- (o total humanos + IAs nunca passa da capacidade).

create table public.bots (
  id              serial primary key,
  nome            text unique not null,
  personalidade   text not null,
  jeito_de_falar  text not null
);

insert into public.bots (nome, personalidade, jeito_de_falar) values
  ('Lia',  'animada e sempre empolgada com o jogo', 'usa gírias leves como "bora", "mano" e "top"'),
  ('Teco', 'competitivo, gosta de desafiar os outros de forma amigável', 'provoca de leve e comemora vitórias'),
  ('Duda', 'calma e paciente, adora ajudar quem está começando', 'explica as coisas de um jeito simples'),
  ('Rafa', 'engraçado, vive fazendo piada', 'faz trocadilhos e ri com "kkkk"'),
  ('Bia',  'estrategista, pensa antes de agir', 'dá dicas táticas curtas'),
  ('Juca', 'novato curioso, ainda aprendendo o jogo', 'faz muitas perguntas'),
  ('Nina', 'adora construir e decorar coisas no jogo', 'fala de ideias criativas'),
  ('Caio', 'speedrunner apressado', 'escreve rápido, frases curtas, às vezes sem pontuação'),
  ('Mel',  'gentil e carinhosa com todo mundo', 'usa emojis com moderação'),
  ('Zeca', 'veterano nostálgico que joga há muito tempo', 'conta como era antigamente'),
  ('Lu',   'tímida mas simpática', 'responde com frases bem curtas'),
  ('Gabi', 'exploradora que conhece todos os cantos do mapa', 'fala de lugares e segredos do mapa');

create table public.bots_dos_servidores (
  server_uid  uuid not null references public.servidores_ativos(server_uid) on delete cascade,
  bot_id      int  not null references public.bots(id) on delete cascade,
  entrou_em   timestamptz not null default now(),
  primary key (server_uid, bot_id)
);

-- mensagens de IA no chat: sem user_id, com bot_id
alter table public.servidores_logados alter column user_id drop not null;
alter table public.servidores_logados
  add column bot_id int references public.bots(id) on delete set null,
  add column respondida boolean not null default false;
alter table public.servidores_logados
  add constraint autor_humano_ou_ia check (user_id is not null or bot_id is not null);

alter table public.bots enable row level security;
alter table public.bots_dos_servidores enable row level security;
create policy "bots visíveis para logados" on public.bots
  for select to authenticated using (true);
create policy "bots dos servidores visíveis para logados" on public.bots_dos_servidores
  for select to authenticated using (true);

-- Ajusta quantas IAs ficam no servidor
create function public.ajustar_bots(p_server uuid)
returns void language plpgsql security definer set search_path = public as $$
declare
  cap int;
  humanos int;
  atuais int;
  alvo int;
begin
  select capacidade into cap from public.servidores_ativos where server_uid = p_server;
  if not found then return; end if;

  select count(*) into humanos from public.users_dos_servidores where server_uid = p_server;
  select count(*) into atuais from public.bots_dos_servidores where server_uid = p_server;
  alvo := greatest(0, least(cap / 2, cap - humanos));   -- divisão inteira: 11 / 2 = 5

  if atuais > alvo then
    delete from public.bots_dos_servidores
     where server_uid = p_server
       and bot_id in (select bot_id from public.bots_dos_servidores
                       where server_uid = p_server
                       order by entrou_em desc, bot_id desc
                       limit atuais - alvo);
  elsif atuais < alvo then
    insert into public.bots_dos_servidores (server_uid, bot_id)
    select p_server, b.id from public.bots b
     where not exists (select 1 from public.bots_dos_servidores x
                        where x.server_uid = p_server and x.bot_id = b.id)
     order by random()
     limit alvo - atuais;
  end if;
end $$;

create function public.ao_mudar_servidor_bots()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if tg_table_name = 'servidores_ativos' then
    perform public.ajustar_bots(new.server_uid);
  elsif tg_op = 'DELETE' then
    perform public.ajustar_bots(old.server_uid);
  else
    perform public.ajustar_bots(new.server_uid);
  end if;
  return null;
end $$;

create trigger bots_ao_criar_servidor
  after insert on public.servidores_ativos
  for each row execute function public.ao_mudar_servidor_bots();

create trigger bots_ao_entrar_ou_sair
  after insert or delete on public.users_dos_servidores
  for each row execute function public.ao_mudar_servidor_bots();

-- Cada mensagem de jogador real chama a Edge Function bots-responder
create function public.chamar_bots()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  perform net.http_post(
    url := 'https://llgriaqnlcylpaxudrlg.supabase.co/functions/v1/bots-responder',
    headers := '{"Content-Type":"application/json"}'::jsonb,
    body := jsonb_build_object('mensagem_id', new.id)
  );
  return null;
end $$;

create trigger bots_responder
  after insert on public.servidores_logados
  for each row when (new.user_id is not null)
  execute function public.chamar_bots();

alter publication supabase_realtime add table public.bots_dos_servidores;

-- servidores que já existem ganham as IAs agora
select public.ajustar_bots(server_uid) from public.servidores_ativos;
