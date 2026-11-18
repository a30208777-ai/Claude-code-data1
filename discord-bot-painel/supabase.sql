-- Rode no Supabase: SQL Editor → New query → cole tudo → Run
-- Guarda o histórico do painel. Só o servidor (service_role) acessa.

create table if not exists public.panel_messages (
  id bigint generated always as identity primary key,
  name text not null,
  guild_id text not null,
  channel_id text not null,
  discord_message_id text not null,
  content text,
  has_file boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.panel_logins (
  id bigint generated always as identity primary key,
  name text not null,
  ip text,
  success boolean not null,
  created_at timestamptz not null default now()
);

create index if not exists panel_messages_created_idx on public.panel_messages (created_at desc);
create index if not exists panel_logins_created_idx on public.panel_logins (created_at desc);

-- RLS ligado e SEM políticas = ninguém de fora lê ou escreve.
-- O bot usa a service_role key, que ignora o RLS.
alter table public.panel_messages enable row level security;
alter table public.panel_logins enable row level security;
