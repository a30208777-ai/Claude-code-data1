-- Projetos do ROLOX Studio salvos na conta do jogador (Studio dentro do site).
-- Cada jogador só vê e mexe nos próprios projetos (RLS).

create table if not exists public.projetos_studio (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nome text not null check (nome ~ '^[A-Za-z0-9_-]{1,40}$'),
  dados jsonb not null,
  tamanho integer not null default 0 check (tamanho between 0 and 5242880),
  atualizado_em timestamptz not null default now(),
  primary key (user_id, nome)
);
alter table public.projetos_studio enable row level security;
create policy projetos_do_dono on public.projetos_studio
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
