-- Parceria: o dono cria uma chave (ex.: 55hjl68!(+7!kjsk)arthurdevpromax.io), manda na DM,
-- e a pessoa usa na aba "Parceria" (logada): a conta vira Parceiro 🤝.
-- Guardamos só o SHA-256 da chave. Cada chave vale para 1 conta; o dono pode revogar.

alter table public.perfis add column if not exists is_parceiro boolean not null default false;
alter table public.perfis add column if not exists parceiro_desde timestamptz;

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
    or new.parceiro_desde is distinct from old.parceiro_desde) then
    raise exception 'campo protegido do perfil' using errcode = '42501';
  end if;
  return new;
end $$;

create table if not exists public.parcerias_chaves (
  id bigint generated always as identity primary key,
  hash text not null unique,
  apelido text not null check (char_length(apelido) between 1 and 40),
  final text not null,                       -- últimos 4 caracteres antes do sufixo (para reconhecer)
  criado_por uuid references public.perfis(id) on delete set null,
  criado_em timestamptz not null default now(),
  usado_por uuid references public.perfis(id) on delete set null,
  usado_em timestamptz,
  revogada boolean not null default false
);
alter table public.parcerias_chaves enable row level security;    -- sem políticas: só pelas funções

create or replace function public.dono_criar_chave_parceria(p_apelido text)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare
  alfabeto constant text := 'abcdefghjkmnpqrstuvwxyz23456789!+()';
  b bytea := gen_random_bytes(18);
  corpo text := '';
  chave text;
  i int;
begin
  perform public.exigir_dono();
  if coalesce(trim(p_apelido), '') = '' then raise exception 'dê um nome para o parceiro' using errcode = 'P0001'; end if;
  for i in 0..17 loop
    corpo := corpo || substr(alfabeto, (get_byte(b, i) % length(alfabeto)) + 1, 1);
  end loop;
  chave := corpo || 'arthurdevpromax.io';
  insert into public.parcerias_chaves (hash, apelido, final, criado_por)
  values (encode(digest(chave, 'sha256'), 'hex'), left(trim(p_apelido), 40), right(corpo, 4), auth.uid());
  return json_build_object('chave', chave, 'apelido', left(trim(p_apelido), 40));
end $$;

create or replace function public.usar_chave_parceria(p_chave text)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare
  eu uuid := auth.uid();
  c public.parcerias_chaves;
begin
  if eu is null then raise exception 'entre na sua conta antes de usar a chave' using errcode = '42501'; end if;
  select * into c from public.parcerias_chaves
   where hash = encode(digest(trim(coalesce(p_chave, '')), 'sha256'), 'hex') for update;
  if not found or c.revogada then raise exception 'chave inválida' using errcode = 'P0001'; end if;
  if c.usado_por is not null and c.usado_por <> eu then raise exception 'essa chave já foi usada por outra conta' using errcode = 'P0001'; end if;
  update public.parcerias_chaves set usado_por = eu, usado_em = coalesce(usado_em, now()) where id = c.id;
  update public.perfis set is_parceiro = true, parceiro_desde = coalesce(parceiro_desde, now()) where id = eu;
  return json_build_object('parceiro', true, 'apelido', c.apelido);
end $$;

create or replace function public.dono_parcerias()
returns json language plpgsql stable security definer set search_path = public as $$
begin
  perform public.exigir_dono();
  return coalesce((select json_agg(x order by x.criado_em desc) from (
    select c.id, c.apelido, c.final, c.criado_em, c.usado_em, c.revogada, p.username as usado_por
      from public.parcerias_chaves c left join public.perfis p on p.id = c.usado_por) x), '[]'::json);
end $$;

create or replace function public.dono_revogar_parceria(p_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare quem uuid;
begin
  perform public.exigir_dono();
  update public.parcerias_chaves set revogada = true where id = p_id returning usado_por into quem;
  if quem is not null and not exists (
       select 1 from public.parcerias_chaves where usado_por = quem and not revogada) then
    update public.perfis set is_parceiro = false where id = quem;
  end if;
end $$;
