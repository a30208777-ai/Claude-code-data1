-- ✍️ "Sobre mim": frase curta no perfil (até 140 letras), passando pelo filtro de palavras do chat.
-- Só muda pela função definir_bio (a coluna não está entre as que o usuário edita direto).

alter table public.perfis add column if not exists bio text not null default '' check (char_length(bio) <= 140);

create or replace function public.definir_bio(p_texto text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  t text := left(regexp_replace(trim(coalesce(p_texto, '')), '\s+', ' ', 'g'), 140);
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if t <> '' then t := left(public.filtrar_texto(t), 140); end if;
  update public.perfis set bio = t where id = eu;
  return json_build_object('bio', t);
end $$;

create or replace function public.perfil_publico(p_username text)
returns json language sql stable security definer set search_path = public as $$
  select json_build_object('username', p.username, 'avatar', p.avatar, 'is_parceiro', p.is_parceiro,
                           'parceiro_desde', p.parceiro_desde,
                           'redes', case when p.is_parceiro then p.redes else '{}'::jsonb end,
                           'criado_em', p.criado_em,
                           'app', public.selo_app(p.app_status, p.app_verificado_em),
                           'bio', p.bio)
    from public.perfis p
   where p.username = lower(trim(p_username)) and not p.banido and auth.uid() is not null
$$;
