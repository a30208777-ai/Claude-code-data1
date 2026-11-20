-- v0.14: Cofre — cada jogo guarda dados do PRÓPRIO jogador (moedas, fase, itens...).
-- Só o dono dos dados lê/grava (pelas funções). Limites: 50 chaves por jogo, valor até 1000 caracteres.
create table if not exists public.cofre (
  mapa_id uuid not null references public.mapas(id) on delete cascade,
  user_id uuid not null references public.perfis(id) on delete cascade,
  chave text not null check (chave ~ '^[A-Za-z0-9_]{1,40}$'),
  valor jsonb not null,
  atualizado_em timestamptz not null default now(),
  primary key (mapa_id, user_id, chave)
);
alter table public.cofre enable row level security;      -- sem políticas: só pelas funções

create or replace function public.cofre_ler(p_mapa uuid)
returns json language sql stable security definer set search_path = public as $$
  select coalesce(json_object_agg(chave, valor), '{}'::json) from public.cofre
   where mapa_id = p_mapa and user_id = auth.uid()
$$;

create or replace function public.cofre_salvar(p_mapa uuid, p_dados jsonb)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  k text; v jsonb;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  if not exists (select 1 from public.mapas where id = p_mapa and caminho_aprovado is not null) then
    raise exception 'jogo não encontrado' using errcode = 'P0001';
  end if;
  if jsonb_typeof(p_dados) <> 'object' then raise exception 'formato inválido' using errcode = 'P0001'; end if;
  for k, v in select key, value from jsonb_each(p_dados) loop
    if k !~ '^[A-Za-z0-9_]{1,40}$' then raise exception 'chave inválida: %', left(k, 40) using errcode = 'P0001'; end if;
    if v is null or jsonb_typeof(v) = 'null' then
      delete from public.cofre where mapa_id = p_mapa and user_id = eu and chave = k;
      continue;
    end if;
    if jsonb_typeof(v) not in ('string', 'number', 'boolean') or char_length(v::text) > 1000 then
      raise exception 'valor inválido em %: use texto, número ou verdadeiro/falso', k using errcode = 'P0001';
    end if;
    insert into public.cofre (mapa_id, user_id, chave, valor) values (p_mapa, eu, k, v)
    on conflict (mapa_id, user_id, chave) do update set valor = excluded.valor, atualizado_em = now();
  end loop;
  if (select count(*) from public.cofre where mapa_id = p_mapa and user_id = eu) > 50 then
    raise exception 'o Cofre aceita até 50 chaves por jogo' using errcode = 'P0001';
  end if;
  return json_build_object('ok', true);
end $$;
