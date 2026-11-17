-- E-mail opcional: fica no perfil (perfis.email), não no Supabase Auth.
-- A conta no Auth usa um e-mail interno <username>@jogador.rolox.invalid
-- criado pela Edge Function `cadastro`.

alter table public.perfis
  add column email text check (email is null or email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$');

create or replace function public.criar_perfil_novo_usuario()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.perfis (id, username, aceitou_localizacao, email)
  values (
    new.id,
    lower(new.raw_user_meta_data ->> 'username'),
    coalesce((new.raw_user_meta_data ->> 'aceitou_localizacao')::boolean, false),
    nullif(lower(btrim(new.raw_user_meta_data ->> 'email_contato')), '')
  );
  return new;
end $$;

-- produção: o jogador também pode editar o próprio e-mail
grant update (email) on public.perfis to authenticated;
