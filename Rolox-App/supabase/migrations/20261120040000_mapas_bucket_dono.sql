-- Mapas do ROLOX num bucket, aprovados pelo DONO antes de aparecerem para todos.
--
--  * Storage: bucket privado "mapas"; cada criador grava só na pasta <user_id>/.
--  * Tabela mapas: versão ENVIADA (em análise) e versão APROVADA (a que todos jogam).
--    Mandar uma versão nova não tira o jogo do ar: o povo continua na aprovada.
--  * Dono: a conta cujo username está em config_servidor ('dono_username').
--    Ele vê e testa os mapas em análise e aprova/recusa. Ao aprovar, o mapa
--    vira um jogo (tabela jogos) e entra na lista "Jogos" com servidores e chat.
--  * Usernames passam a aceitar "." e "_" (ex.: arthurdevpromax.off_dono).
--    O nome do dono é RESERVADO: o cadastro só cria com o código do dono
--    (config_servidor 'dono_codigo', que não vai para o Git).

-- ------------------------------------------------------------ usernames
alter table public.perfis drop constraint perfis_username_check;
alter table public.perfis add constraint perfis_username_check
  check (username ~ '^[a-z0-9]([a-z0-9._-]{1,30}[a-z0-9])$');

insert into public.config_servidor (nome, valor) values ('dono_username', 'arthurdevpromax.off_dono')
on conflict (nome) do update set valor = excluded.valor, atualizado_em = now();

-- ------------------------------------------------------------ dono
create or replace function public.eh_dono()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.perfis p
      join public.config_servidor c on c.nome = 'dono_username' and c.valor = p.username
     where p.id = auth.uid() and not p.banido)
$$;

create or replace function public.exigir_dono()
returns void language plpgsql stable security definer set search_path = public as $$
begin
  if not public.eh_dono() then
    raise exception 'apenas o dono' using errcode = '42501';
  end if;
end $$;

-- ------------------------------------------------------------ tabela
create table if not exists public.mapas (
  id uuid primary key,
  autor_id uuid not null references public.perfis(id) on delete cascade,
  nome text not null check (char_length(nome) between 1 and 40),
  descricao text not null default '' check (char_length(descricao) <= 300),
  caminho_enviado text,
  caminho_aprovado text,
  status text not null default 'em_analise' check (status in ('em_analise', 'aprovado', 'recusado')),
  motivo text,
  gameid text unique references public.jogos(gameid),
  criado_em timestamptz not null default now(),
  enviado_em timestamptz not null default now(),
  aprovado_em timestamptz
);
create index if not exists mapas_status on public.mapas (status, enviado_em);

alter table public.mapas enable row level security;
create policy "mapas: autor, dono ou publicado" on public.mapas for select
  using (autor_id = auth.uid() or caminho_aprovado is not null or public.eh_dono());

-- ------------------------------------------------------------ RPCs
-- O app grava o arquivo em mapas/<user_id>/<mapa_id>/<versão>.json e depois chama isto.
create or replace function public.enviar_mapa(p_id uuid, p_nome text, p_descricao text, p_caminho text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  m public.mapas;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if p_caminho is null or p_caminho !~ ('^' || eu::text || '/' || p_id::text || '/[A-Za-z0-9-]{1,40}\.json$') then
    raise exception 'caminho inválido' using errcode = 'P0001';
  end if;
  if not exists (select 1 from storage.objects where bucket_id = 'mapas' and name = p_caminho) then
    raise exception 'arquivo do mapa não encontrado' using errcode = 'P0001';
  end if;
  select * into m from public.mapas where id = p_id;
  if found and m.autor_id <> eu then raise exception 'mapa de outra pessoa' using errcode = '42501'; end if;
  if (select count(*) from public.mapas where autor_id = eu and status = 'em_analise' and id <> p_id) >= 10 then
    raise exception 'você já tem 10 mapas em análise; espere o dono olhar' using errcode = 'P0001';
  end if;
  insert into public.mapas (id, autor_id, nome, descricao, caminho_enviado, status, motivo, enviado_em)
  values (p_id, eu, left(trim(p_nome), 40), left(coalesce(trim(p_descricao), ''), 300), p_caminho, 'em_analise', null, now())
  on conflict (id) do update set nome = excluded.nome, descricao = excluded.descricao,
    caminho_enviado = excluded.caminho_enviado, status = 'em_analise', motivo = null, enviado_em = now();
  return json_build_object('id', p_id, 'status', 'em_analise');
end $$;

create or replace function public.dono_aprovar_mapa(p_id uuid)
returns json language plpgsql security definer set search_path = public as $$
declare
  m public.mapas;
  gid text;
begin
  perform public.exigir_dono();
  select * into m from public.mapas where id = p_id for update;
  if not found or m.caminho_enviado is null then raise exception 'mapa não encontrado' using errcode = 'P0001'; end if;
  gid := coalesce(m.gameid, 'mapa-' || left(replace(m.id::text, '-', ''), 12));
  insert into public.jogos (gameid, nome, repo, branch, commit_aprovado, aprovado_por, aprovado_em)
  values (gid, m.nome, 'bucket:mapas', 'aprovado', m.caminho_enviado, auth.uid(), now())
  on conflict (gameid) do update set nome = excluded.nome, commit_aprovado = excluded.commit_aprovado,
    aprovado_por = excluded.aprovado_por, aprovado_em = excluded.aprovado_em;
  update public.mapas set caminho_aprovado = caminho_enviado, status = 'aprovado', motivo = null,
         gameid = gid, aprovado_em = now() where id = p_id;
  return json_build_object('id', p_id, 'gameid', gid, 'status', 'aprovado');
end $$;

create or replace function public.dono_recusar_mapa(p_id uuid, p_motivo text)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  update public.mapas set status = 'recusado', motivo = left(coalesce(trim(p_motivo), ''), 300)
   where id = p_id and status = 'em_analise';
  if not found then raise exception 'mapa não está em análise' using errcode = 'P0001'; end if;
  return json_build_object('id', p_id, 'status', 'recusado');
end $$;

-- ------------------------------------------------------------ Storage
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('mapas', 'mapas', false, 5242880, array['application/json'])
on conflict (id) do nothing;

create policy "mapas: criador envia na própria pasta" on storage.objects for insert to authenticated
  with check (bucket_id = 'mapas' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "mapas: criador, dono ou aprovado podem ler" on storage.objects for select to authenticated
  using (bucket_id = 'mapas' and (
    (storage.foldername(name))[1] = auth.uid()::text
    or public.eh_dono()
    or exists (select 1 from public.mapas m where m.caminho_aprovado = storage.objects.name)));
