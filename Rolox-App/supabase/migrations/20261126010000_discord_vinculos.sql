-- 🔗 Ligar a conta do Discord à conta do VISTA (feito pelo site depois do login com o Discord).
create table if not exists public.discord_vinculos (
  user_id uuid primary key references public.perfis(id) on delete cascade,
  discord_id text not null unique check (discord_id ~ '^[0-9]{5,25}$'),
  discord_nome text,
  ligado_em timestamptz not null default now()
);
alter table public.discord_vinculos enable row level security;

create or replace function public.ligar_discord(p_discord_id text, p_discord_nome text)
returns json language plpgsql security definer set search_path = public as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if exists (select 1 from public.discord_vinculos where discord_id = p_discord_id and user_id <> eu) then
    raise exception 'esse Discord já está ligado a outra conta do VISTA';
  end if;
  insert into public.discord_vinculos (user_id, discord_id, discord_nome) values (eu, p_discord_id, left(p_discord_nome, 64))
  on conflict (user_id) do update set discord_id = excluded.discord_id, discord_nome = excluded.discord_nome, ligado_em = now();
  return json_build_object('ok', true);
end $$;

create or replace function public.desligar_discord()
returns json language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  delete from public.discord_vinculos where user_id = auth.uid();
  return json_build_object('ok', true);
end $$;

create or replace function public.meu_discord()
returns json language sql stable security definer set search_path = public as $$
  select coalesce((select json_build_object('discord_id', discord_id, 'discord_nome', discord_nome, 'ligado_em', ligado_em)
                     from public.discord_vinculos where user_id = auth.uid()), '{}'::json)
$$;

create or replace function public.discord_de(p_username text)
returns text language plpgsql stable security definer set search_path = public as $$
begin
  if not public.eh_equipe() then raise exception 'apenas a equipe' using errcode = '42501'; end if;
  return (select v.discord_id from public.discord_vinculos v join public.perfis p on p.id = v.user_id
           where p.username = lower(trim(p_username)));
end $$;
