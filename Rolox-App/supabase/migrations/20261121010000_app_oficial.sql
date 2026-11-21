-- App oficial: o dono cadastra a "proctetion" do Vision-apk-link.json (como uma chave de parceria)
-- e o app ROLOX manda essa chave ao abrir. Quem manda a chave certa fica ✅ (app oficial);
-- quem manda errado (app modificado) fica ❌. Quem nunca abriu pelo app não tem marca.
-- Guardamos só o SHA-256 das chaves. O ✅ vale por 7 dias (o app confere toda vez que abre).

alter table public.perfis add column if not exists app_status text check (app_status in ('oficial', 'modificado'));
alter table public.perfis add column if not exists app_verificado_em timestamptz;
alter table public.perfis add column if not exists app_versao text check (char_length(app_versao) <= 20);

-- os campos do app só mudam pela função verificar_app
create or replace function public.proteger_perfil()
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
    or new.tickets_ultimo_dia is distinct from old.tickets_ultimo_dia
    or new.sem_chat_ate is distinct from old.sem_chat_ate
    or new.sem_chat_motivo is distinct from old.sem_chat_motivo
    or new.is_parceiro is distinct from old.is_parceiro
    or new.parceiro_desde is distinct from old.parceiro_desde
    or new.redes is distinct from old.redes
    or new.app_status is distinct from old.app_status
    or new.app_verificado_em is distinct from old.app_verificado_em
    or new.app_versao is distinct from old.app_versao) then
    raise exception 'campo protegido do perfil' using errcode = '42501';
  end if;
  return new;
end $$;

create table if not exists public.chaves_app (
  id bigint generated always as identity primary key,
  hash text not null unique,
  apelido text not null check (char_length(apelido) between 1 and 40),
  final text not null,                      -- últimos 4 caracteres (para o dono reconhecer)
  criado_por uuid references public.perfis(id) on delete set null,
  criado_em timestamptz not null default now(),
  revogada boolean not null default false,
  usos bigint not null default 0
);
alter table public.chaves_app enable row level security;     -- sem políticas: só pelas funções

-- marca mostrada ao lado do nome: 'oficial' (✅), 'modificado' (❌) ou null (sem marca)
create or replace function public.selo_app(p_status text, p_em timestamptz)
returns text language sql stable as $$
  select case when p_status = 'modificado' then 'modificado'
              when p_status = 'oficial' and p_em > now() - interval '7 days' then 'oficial'
              else null end
$$;

create or replace function public.dono_adicionar_chave_app(p_chave text, p_apelido text)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare
  k text := trim(coalesce(p_chave, ''));
begin
  perform public.exigir_dono();
  if char_length(k) < 16 or char_length(k) > 1000 then
    raise exception 'a chave precisa ter de 16 a 1000 caracteres' using errcode = 'P0001';
  end if;
  if coalesce(trim(p_apelido), '') = '' then raise exception 'dê um nome para a chave (ex.: versão 0.20)' using errcode = 'P0001'; end if;
  insert into public.chaves_app (hash, apelido, final, criado_por)
  values (encode(digest(k, 'sha256'), 'hex'), left(trim(p_apelido), 40), right(k, 4), auth.uid())
  on conflict (hash) do update set revogada = false, apelido = excluded.apelido;
  return json_build_object('ok', true, 'apelido', left(trim(p_apelido), 40));
end $$;

create or replace function public.dono_chaves_app()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  return json_build_object(
    'chaves', coalesce((select json_agg(x order by x.criado_em desc) from (
       select id, apelido, final, criado_em, revogada, usos from public.chaves_app) x), '[]'::json),
    'oficiais', (select count(*) from public.perfis where public.selo_app(app_status, app_verificado_em) = 'oficial'),
    'modificados', (select count(*) from public.perfis where app_status = 'modificado'),
    'lista_modificados', coalesce((select json_agg(x) from (
       select username, app_versao, app_verificado_em from public.perfis
        where app_status = 'modificado' order by app_verificado_em desc nulls last limit 50) x), '[]'::json));
end $$;

create or replace function public.dono_revogar_chave_app(p_id bigint)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  update public.chaves_app set revogada = true where id = p_id;
end $$;

-- o app ROLOX chama ao abrir (com a proctetion lida do Vision-apk-link.json)
create or replace function public.verificar_app(p_chave text, p_versao text default null)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare
  eu uuid := auth.uid();
  achou bigint;
  status text;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  -- o dono ainda não cadastrou nenhuma chave: não dá para julgar ninguém
  if not exists (select 1 from public.chaves_app where not revogada) then
    return json_build_object('status', 'sem_chave_cadastrada');
  end if;
  select id into achou from public.chaves_app
   where not revogada and hash = encode(digest(trim(coalesce(p_chave, '')), 'sha256'), 'hex');
  status := case when achou is null then 'modificado' else 'oficial' end;
  if achou is not null then update public.chaves_app set usos = usos + 1 where id = achou; end if;
  update public.perfis set app_status = status, app_verificado_em = now(),
                           app_versao = left(nullif(trim(coalesce(p_versao, '')), ''), 20)
   where id = eu;
  return json_build_object('status', status);
end $$;

-- perfil público e busca passam a dizer a marca do app
create or replace function public.perfil_publico(p_username text)
returns json language sql stable security definer set search_path = public as $$
  select json_build_object('username', p.username, 'avatar', p.avatar, 'is_parceiro', p.is_parceiro,
                           'parceiro_desde', p.parceiro_desde,
                           'redes', case when p.is_parceiro then p.redes else '{}'::jsonb end,
                           'criado_em', p.criado_em,
                           'app', public.selo_app(p.app_status, p.app_verificado_em))
    from public.perfis p
   where p.username = lower(trim(p_username)) and not p.banido and auth.uid() is not null
$$;

create or replace function public.buscar_jogadores(p_termo text, p_limite int default 20)
returns json language plpgsql stable security definer set search_path = public as $$
declare
  t text := lower(trim(coalesce(p_termo, '')));
  esc text;
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if char_length(t) < 2 or char_length(t) > 32 then return '[]'::json; end if;
  esc := replace(replace(replace(t, '\', '\\'), '%', '\%'), '_', '\_');
  return coalesce((select json_agg(x) from (
    select p.username, p.avatar, p.is_parceiro, public.selo_app(p.app_status, p.app_verificado_em) as app,
           case when p.username = t then 0
                when p.username like esc || '%' then 1
                when p.username ~ ('[._-]' || regexp_replace(t, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g')) then 2
                else 3 end as nivel
      from public.perfis p
     where not p.banido and p.username like '%' || esc || '%'
     order by nivel, char_length(p.username), p.username
     limit greatest(1, least(p_limite, 50))) x), '[]'::json);
end $$;
