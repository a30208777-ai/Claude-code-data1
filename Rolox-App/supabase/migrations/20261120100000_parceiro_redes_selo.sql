-- Parceiros: redes sociais (só links das redes conhecidas) + selo 🤝 ao lado do nome.
alter table public.perfis add column if not exists redes jsonb not null default '{}'::jsonb
  check (jsonb_typeof(redes) = 'object' and pg_column_size(redes) < 2000);

-- redes só mudam pela função (que exige ser parceiro e valida os links)
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
    or new.redes is distinct from old.redes) then
    raise exception 'campo protegido do perfil' using errcode = '42501';
  end if;
  return new;
end $$;

-- rede -> padrão do link aceito (https e o domínio da própria rede)
create or replace function public.rede_valida(p_rede text, p_url text)
returns boolean language sql immutable as $$
  select char_length(p_url) <= 200 and p_url !~ '[\s<>"''`]' and case p_rede
    when 'youtube'   then p_url ~* '^https://(www\.|m\.)?(youtube\.com|youtu\.be)/[^\s]+$'
    when 'tiktok'    then p_url ~* '^https://(www\.|vm\.)?tiktok\.com/[^\s]+$'
    when 'instagram' then p_url ~* '^https://(www\.)?instagram\.com/[^\s]+$'
    when 'twitch'    then p_url ~* '^https://(www\.|m\.)?twitch\.tv/[^\s]+$'
    when 'discord'   then p_url ~* '^https://(www\.)?(discord\.gg|discord\.com/invite)/[^\s]+$'
    when 'x'         then p_url ~* '^https://(www\.)?(x\.com|twitter\.com)/[^\s]+$'
    when 'kwai'      then p_url ~* '^https://(www\.|m\.)?kwai\.com/[^\s]+$'
    else false end
$$;

create or replace function public.definir_redes(p_redes jsonb)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  limpo jsonb := '{}'::jsonb;
  k text; v text;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if not exists (select 1 from public.perfis where id = eu and is_parceiro and not banido) then
    raise exception 'só parceiros podem colocar redes sociais' using errcode = '42501';
  end if;
  if jsonb_typeof(coalesce(p_redes, '{}'::jsonb)) <> 'object' then raise exception 'formato inválido' using errcode = 'P0001'; end if;
  for k, v in select key, value from jsonb_each_text(coalesce(p_redes, '{}'::jsonb)) loop
    v := trim(coalesce(v, ''));
    continue when v = '';
    if not public.rede_valida(k, v) then
      raise exception 'link inválido para %: use o link https da própria rede', k using errcode = 'P0001';
    end if;
    limpo := limpo || jsonb_build_object(k, v);
  end loop;
  update public.perfis set redes = limpo where id = eu;
  return json_build_object('redes', limpo);
end $$;

-- página pública do jogador (redes só aparecem para parceiros)
create or replace function public.perfil_publico(p_username text)
returns json language sql stable security definer set search_path = public as $$
  select json_build_object('username', p.username, 'avatar', p.avatar, 'is_parceiro', p.is_parceiro,
                           'parceiro_desde', p.parceiro_desde,
                           'redes', case when p.is_parceiro then p.redes else '{}'::jsonb end,
                           'criado_em', p.criado_em)
    from public.perfis p
   where p.username = lower(trim(p_username)) and not p.banido and auth.uid() is not null
$$;

-- quais desses nomes são parceiros (para o selo no chat, ranking, mapa...)
create or replace function public.parceiros_entre(p_nomes text[])
returns text[] language sql stable security definer set search_path = public as $$
  select coalesce(array_agg(username), '{}') from public.perfis
   where is_parceiro and not banido and username = any(p_nomes[1:200]) and auth.uid() is not null
$$;
