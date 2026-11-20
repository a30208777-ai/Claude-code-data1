-- Site do Rolox no Render: o servidor do site informa às Edge Functions
-- (login-protegido e cadastro) o IP real do jogador, assinado com uma chave.
-- A chave fica aqui (nome = 'proxy_chave'); RLS ligado e sem políticas:
-- só a service_role (as Edge Functions) consegue ler. O valor NÃO vai para o Git:
--   insert into public.config_servidor (nome, valor) values ('proxy_chave', '<chave>')
--   on conflict (nome) do update set valor = excluded.valor, atualizado_em = now();
-- e a mesma chave vai na variável ROLOX_PROXY_CHAVE do serviço no Render.

create table if not exists public.config_servidor (
  nome text primary key,
  valor text not null,
  atualizado_em timestamptz not null default now()
);

alter table public.config_servidor enable row level security;
