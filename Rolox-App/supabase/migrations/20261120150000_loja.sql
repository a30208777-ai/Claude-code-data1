-- v0.18: Loja — cores especiais do avatar compradas com tickets.
-- O banco confere: ninguém usa item da loja sem ter comprado (nem mexendo direto no perfil).
create table if not exists public.loja_itens (
  codigo text primary key check (codigo ~ '^[a-z0-9_]{1,40}$'),
  nome text not null,
  campo text not null check (campo in ('camisa', 'calca', 'cor_cabelo', 'pele', 'acessorio', 'cabelo')),
  valor text not null,
  preco integer not null check (preco between 0 and 100000),
  emoji text not null default '🎨',
  ativo boolean not null default true,
  unique (campo, valor)
);
alter table public.loja_itens enable row level security;
create policy "loja: todos logados veem" on public.loja_itens for select to authenticated using (ativo);

insert into public.loja_itens (codigo, nome, campo, valor, preco, emoji) values
  ('camisa_dourada', 'Camisa Dourada', 'camisa', '#ffc400', 60, '👕'),
  ('camisa_neon', 'Camisa Neon azul', 'camisa', '#00e5ff', 40, '👕'),
  ('camisa_galaxia', 'Camisa Galáxia', 'camisa', '#311b92', 50, '👕'),
  ('calca_dourada', 'Calça Dourada', 'calca', '#ffc400', 60, '👖'),
  ('calca_prata', 'Calça Prata', 'calca', '#b0bec5', 35, '👖'),
  ('cabelo_rosa_neon', 'Cabelo Rosa neon', 'cor_cabelo', '#ff4081', 30, '🎨'),
  ('cabelo_verde_neon', 'Cabelo Verde neon', 'cor_cabelo', '#00e676', 30, '🎨'),
  ('cabelo_prata', 'Cabelo Prata', 'cor_cabelo', '#b0bec5', 25, '🎨')
on conflict (codigo) do nothing;

create table if not exists public.itens_comprados (
  user_id uuid not null references public.perfis(id) on delete cascade,
  codigo text not null references public.loja_itens(codigo),
  comprado_em timestamptz not null default now(),
  primary key (user_id, codigo)
);
alter table public.itens_comprados enable row level security;
create policy "compras: vejo as minhas" on public.itens_comprados for select using (user_id = auth.uid());

create or replace function public.comprar_item(p_codigo text)
returns json language plpgsql security definer set search_path = public as $$
declare
  eu uuid := auth.uid();
  it public.loja_itens;
  restante bigint;
  adm boolean;
begin
  if eu is null then raise exception 'entre na conta' using errcode = '42501'; end if;
  select * into it from public.loja_itens where codigo = p_codigo and ativo;
  if not found then raise exception 'item não encontrado' using errcode = 'P0001'; end if;
  if exists (select 1 from public.itens_comprados where user_id = eu and codigo = p_codigo) then
    return json_build_object('ok', true, 'ja_tinha', true);
  end if;
  select is_adm into adm from public.perfis where id = eu;
  if not coalesce(adm, false) then
    update public.perfis set tickets = tickets - it.preco where id = eu and tickets >= it.preco and not banido
    returning tickets into restante;
    if not found then raise exception 'tickets insuficientes: % custa % tickets', it.nome, it.preco using errcode = 'P0001'; end if;
    insert into public.historico_tickets (user_id, delta, motivo) values (eu, -it.preco, 'Loja: ' || it.nome);
  end if;
  insert into public.itens_comprados (user_id, codigo) values (eu, p_codigo);
  return json_build_object('ok', true, 'tickets', restante, 'campo', it.campo, 'valor', it.valor);
end $$;

-- proteção: o avatar só pode ter item da loja se a pessoa comprou
create or replace function public.proteger_avatar_loja()
returns trigger language plpgsql as $$
declare it record;
begin
  if current_user not in ('authenticated', 'anon') or new.avatar is not distinct from old.avatar then return new; end if;
  for it in select * from public.loja_itens loop
    if new.avatar ->> it.campo = it.valor and (old.avatar ->> it.campo) is distinct from it.valor
       and not exists (select 1 from public.itens_comprados c where c.user_id = new.id and c.codigo = it.codigo) then
      raise exception 'compre "%" na Loja antes de usar', it.nome using errcode = '42501';
    end if;
  end loop;
  return new;
end $$;
drop trigger if exists proteger_avatar_loja on public.perfis;
create trigger proteger_avatar_loja before update on public.perfis
  for each row execute function public.proteger_avatar_loja();
