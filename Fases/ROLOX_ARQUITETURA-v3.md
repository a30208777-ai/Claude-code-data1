# ROLOX — Arquitetura Técnica, Plano Completo (20 Fases) e Diretrizes — v3

Plataforma **Rolox**: jogos para PC e celular focados em comunidade, transparência, segurança, servidores customizados e sincronização em tempo real.

> **O que mudou da v2 para a v3**
> - Login: o ban de IP vale **só para quem errou a senha**; o dono da conta recebe um aviso no jogo/página inicial com a senha que foi tentada.
> - `credencial_backup` e senhas tentadas são **criptografadas** e transportadas em **base64**.
> - Autenticação usa o **Supabase Auth**; dados extras ficam na tabela `perfis`.
> - As tabelas de tempo real foram reorganizadas (`server_uid` sem hífen, `is_hack_server`, heartbeat, chat separado dos itens).
> - Acesso por dispositivo: **PC usa subdomínios**, **celular acessa direto as bases de dados** (protegido por RLS).
> - Mapas do GitHub só entram no catálogo **depois da aprovação do dono**.
> - Nova fase de **netcode da partida** (o Supabase Realtime não serve para física/posição em alta frequência).
> - Anticheat nos servidores limpos, autenticação no streaming Flask, regras de LGPD.
> - Painel admin básico adiantado para a Fase 5; **testes em toda fase**, não só na última.

---

## 1. Visão Geral e Prioridades (1 a 10)

### 1.1 Banco de Dados Unificado e Autenticação Blindada (Supabase) — 10/10
* Banco 100% no **Supabase** (substitui o MongoDB Atlas).
* Login e senhas pelo **Supabase Auth** (`auth.users`); dados do jogador na tabela `perfis`.
* **Política de bloqueio (3 tentativas):**
  * Quem errar a senha de uma conta 3 vezes tem o **próprio IP banido** (`ips_bloqueados`).
  * A conta **não** é banida. O dono recebe um **alerta de segurança** no jogo ou na página inicial: *"Alguém tentou entrar na sua conta"*, com o IP, a data e a senha que foi usada.
* `credencial_backup` e senhas tentadas: criptografia (AES via `pgcrypto`) + codificação **base64** para transporte.

### 1.2 Sincronização em Tempo Real (Supabase Realtime) — 10/10
* Tabelas: `servidores_ativos`, `users_dos_servidores`, `espera`, `locate_users`, `servidores_logados` (chat) e `itens_sessao`.
* Realtime cuida de **chat, presença, fila e localização**. Posição/física da partida fica com o servidor de jogo (Fase 13).

### 1.3 IA Tradutora e Moderação Contextual ("SELECT") — 9/10
* Traduz e filtra em tempo real preservando o sentido (ex.: *"hj eu achei um cão mais era a porra de uma sacola"* → *"hj eu achei um cão mais era uma sacola"*).
* Filtro local rápido primeiro; a IA só é chamada quando necessário.

### 1.4 Servidores Separados para Hacks e Mods — 9/10
* Hacks e mods são permitidos, mas só em **servidores dedicados** (`is_hack_server = true`).
* Servidores limpos têm **anticheat** (repositório `rolox-anticheat`) para pegar quem não marcou o modo hack.

### 1.5 Mapas via GitHub — 8/10
* Mapas versionados no GitHub; **cada versão passa pela aprovação do dono** antes de ir ao catálogo.
* O cliente PC baixa o mapa aprovado, confere o checksum e inicia o jogo.

### 1.6 Acesso por Dispositivo — 8/10
* **PC:** subdomínio dinâmico `https://ROLOX.bass.{username}.{gameid}.com/index.html`.
* **Celular:** acessa diretamente as bases de dados do Supabase pelo SDK, com RLS garantindo que cada um só lê/escreve o que pode.

### 1.7 Tela de Perfil e Gestão de Jogos/Mods — 7/10
* O usuário escolhe em qual jogo usa mods/hacks, com troca rápida no menu `config`.

### 1.8 Transmissão de Tela via Flask (Python) — 7/10
* `app.py` com rota `/stream` **autenticada**, para testes mobile/Termux.

---

## 2. Esquema do Banco (SQL de referência)

```sql
create extension if not exists pgcrypto;
create extension if not exists citext;

-- ===== Perfis (ligado ao Supabase Auth) =====
create table perfis (
  id                    uuid primary key references auth.users(id) on delete cascade,
  username              citext unique not null
                        check (username ~ '^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$'), -- válido em subdomínio
  idioma                text not null default 'pt-BR',
  banido                boolean not null default false,          -- só por decisão de moderador
  motivo_ban            text,
  jogo_mod              text references jogos(gameid),           -- jogo com hack/mod ativo (null = nenhum)
  aceitou_localizacao   boolean not null default false,          -- LGPD
  ips_confiaveis        inet[] not null default '{}',            -- IPs onde o dono já logou com sucesso
  is_admin              boolean not null default false,
  criado_em             timestamptz not null default now()
);

-- ===== Segurança de login =====
create table ips_bloqueados (
  ip             inet primary key,
  conta_alvo     uuid references perfis(id),   -- conta que o IP tentou invadir
  motivo         text not null default '3 tentativas de senha errada',
  bloqueado_por  uuid references perfis(id),   -- null = automático
  bloqueado_em   timestamptz not null default now()
);

create table tentativas_login (
  id                     bigserial primary key,
  conta_alvo             uuid not null references perfis(id) on delete cascade,
  ip                     inet not null,
  senha_tentada_cifrada  text not null,        -- base64(pgp_sym_encrypt(senha, chave_servidor))
  criado_em              timestamptz not null default now()
);
create index on tentativas_login (conta_alvo, ip, criado_em);

create table alertas_seguranca (
  id                     bigserial primary key,
  user_id                uuid not null references perfis(id) on delete cascade,
  ip                     inet not null,
  senha_tentada_cifrada  text not null,
  ip_foi_banido          boolean not null default false,
  lido                   boolean not null default false,
  criado_em              timestamptz not null default now()
);

create table credenciais_backup (
  user_id        uuid primary key references perfis(id) on delete cascade,
  credencial     text not null,               -- base64(pgp_sym_encrypt(...))
  criado_em      timestamptz not null default now()
);

-- ===== Catálogo de jogos/mapas (GitHub) =====
create table jogos (
  gameid           text primary key check (gameid ~ '^[a-z0-9-]{2,40}$'),
  nome             text not null,
  repo             text not null,             -- ex.: one-mapas-officeal/mapa-x
  branch           text not null default 'main',
  commit_aprovado  text,                      -- só esse commit é baixado
  sha256           text,                      -- checksum do pacote aprovado
  aprovado_por     uuid references perfis(id),
  aprovado_em      timestamptz
);

-- ===== Tempo real =====
create table servidores_ativos (
  server_uid        uuid primary key default gen_random_uuid(),
  gameid            text not null references jogos(gameid),
  host_id           uuid not null references perfis(id),
  capacidade        int  not null check (capacidade > 0),
  is_hack_server    boolean not null default false,
  status            text not null default 'aberto' check (status in ('aberto','cheio','encerrando')),
  ultimo_heartbeat  timestamptz not null default now(),
  criado_em         timestamptz not null default now()
);

create table users_dos_servidores (
  server_uid  uuid not null references servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references perfis(id) on delete cascade,
  entrou_em   timestamptz not null default now(),
  primary key (server_uid, user_id)
);

create table espera (
  id          bigserial primary key,
  server_uid  uuid not null references servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references perfis(id) on delete cascade,
  entrou_em   timestamptz not null default now(),
  unique (server_uid, user_id)
);

create table locate_users (
  user_id        uuid primary key references perfis(id) on delete cascade,
  locate         text not null,               -- 'menu' | 'lobby' | 'jogo' | 'hack'
  server_uid     uuid references servidores_ativos(server_uid) on delete set null,
  atualizado_em  timestamptz not null default now()
);

-- chat da sessão
create table servidores_logados (
  id                 bigserial primary key,
  server_uid         uuid not null references servidores_ativos(server_uid) on delete cascade,
  user_id            uuid not null references perfis(id) on delete cascade,
  username           citext not null,
  mensagem_original  text not null,           -- apagada após 30 dias (LGPD)
  mensagem_filtrada  text not null,
  idioma_original    text,
  criado_em          timestamptz not null default now()
);

create table itens_sessao (
  server_uid  uuid not null references servidores_ativos(server_uid) on delete cascade,
  user_id     uuid not null references perfis(id) on delete cascade,
  item_id     text not null,
  quantidade  int  not null default 1,
  primary key (server_uid, user_id, item_id)
);

-- Realtime
alter publication supabase_realtime add table
  servidores_ativos, users_dos_servidores, espera, locate_users,
  servidores_logados, itens_sessao, alertas_seguranca;

-- RLS ligado em TODAS as tabelas (o celular acessa direto, então isso é obrigatório)
alter table perfis               enable row level security;
alter table ips_bloqueados       enable row level security;
alter table tentativas_login     enable row level security;
alter table alertas_seguranca    enable row level security;
alter table credenciais_backup   enable row level security;
alter table jogos                enable row level security;
alter table servidores_ativos    enable row level security;
alter table users_dos_servidores enable row level security;
alter table espera               enable row level security;
alter table locate_users         enable row level security;
alter table servidores_logados   enable row level security;
alter table itens_sessao         enable row level security;

-- Exemplos de políticas
create policy "perfil: dono lê e edita" on perfis
  for all using (auth.uid() = id) with check (auth.uid() = id);
create policy "alertas: só o dono vê" on alertas_seguranca
  for select using (auth.uid() = user_id);
create policy "alertas: dono marca como lido" on alertas_seguranca
  for update using (auth.uid() = user_id);
create policy "jogos: catálogo aprovado é público" on jogos
  for select using (commit_aprovado is not null);
create policy "chat: membros do servidor leem" on servidores_logados
  for select using (exists (
    select 1 from users_dos_servidores u
    where u.server_uid = servidores_logados.server_uid and u.user_id = auth.uid()));
-- tentativas_login, ips_bloqueados e credenciais_backup: sem política pública,
-- só o backend (service_role) acessa.
```

> Observação: a tabela `jogos` precisa ser criada antes de `perfis` (por causa de `jogo_mod`). No script real, ordene: `jogos` → `perfis` → resto.

---

## 3. Plano de Execução (Fases 1 a 20)

> **Regra geral:** cada fase só termina com seus testes automatizados passando no CI. A Fase 20 é o teste de carga final, não o primeiro teste.

### Fase 1: Estrutura Base e CI
* Criar `/backend`, `/client-pc`, `/client-mobile`, `/game-server`, `/streaming-flask`, `/database-sql` e `/docs`.
* `.env.example` com chaves do Supabase, token do GitHub (só no backend), chave de criptografia e segredos JWT.
* Pipeline de CI (GitHub Actions) rodando lint e testes em cada push.

### Fase 2: Supabase Auth, Perfis e RLS
* Ativar Supabase Auth (e-mail + senha; 2FA opcional).
* Criar `jogos`, `perfis` e trigger que cria o perfil ao cadastrar.
* Ativar RLS em todas as tabelas com as políticas da seção 2.

### Fase 3: Login Protegido — 3 Tentativas, Ban do IP Atacante e Aviso ao Dono
* Endpoint `/auth/login` no backend (ou Edge Function):
  1. Se o IP está em `ips_bloqueados` → recusa na hora.
  2. Tenta logar no Supabase Auth.
  3. **Erro:** grava em `tentativas_login` a senha tentada (criptografada + base64) e cria um `alertas_seguranca` para o dono.
  4. **3ª falha do mesmo IP na mesma conta (janela de 24 h):** insere o IP em `ips_bloqueados` e marca `ip_foi_banido = true` no alerta.
  5. **Sucesso:** adiciona o IP em `ips_confiaveis` e zera o contador daquele IP.
* O dono vê o alerta (via Realtime) no jogo ou na página inicial: *"Alguém tentou entrar na sua conta — IP x.x.x.x — senha usada: \*\*\*\*\* (toque para ver)"*. A senha só é decifrada no backend e entregue ao dono logado.
* **Exceção:** se o IP está em `ips_confiaveis` do próprio dono (ele mesmo errou), não bane; pede confirmação por e-mail.
* Senhas tentadas e alertas são apagados depois de 30 dias.

### Fase 4: Recuperação de Conta e Credencial de Backup
* Gerar `credencial_backup` no cadastro, mostrar uma vez ao usuário e guardar criptografada + base64.
* Endpoint de recuperação: valida a credencial e permite trocar a senha.
* Endpoint administrativo para desbloquear IP/conta.

### Fase 5: Painel Admin Básico
* Tela restrita (`is_admin`) com IPs bloqueados, alertas recentes e botão de banir/desbanir IP.
* Fica pronto cedo para dar suporte às Fases 3 e 4 desde o começo.

### Fase 6: Tabelas de Tempo Real
* Criar `servidores_ativos`, `users_dos_servidores`, `espera`, `locate_users`, `servidores_logados` e `itens_sessao`.
* Adicionar todas à publicação `supabase_realtime`.

### Fase 7: Gerenciador de Servidores (`servidores_ativos`)
* Registrar novo `server_uid` com `gameid`, `host_id`, `capacidade` e `is_hack_server`.
* Heartbeat a cada 15 s; tarefa agendada (pg_cron) remove servidores sem heartbeat há mais de 60 s ou vazios.

### Fase 8: Alocação de Jogadores e Fila de Espera
* Função SQL transacional `entrar_servidor(server_uid)` que confere a capacidade com lock (evita dois jogadores pegarem a última vaga).
* Servidor cheio → insere em `espera`; quando sai alguém, o primeiro da fila é promovido e notificado via Realtime.

### Fase 9: Localização Cross-Device (`locate_users`)
* Atualiza `locate` a cada mudança de estado (menu, lobby, jogo, hack).
* Só grava se `aceitou_localizacao = true` (LGPD). Amigos e admin veem o status.

### Fase 10: Tela de Perfil, Seletor de Hack/Mod e Menu `config`
* Perfil lista os jogos do catálogo; usuário marca `jogo_mod`.
* Rota `/profile/config/mod-game` para trocar ou desativar a qualquer momento.
* Se mudar no meio de uma partida incompatível → desconexão limpa e volta ao lobby.

### Fase 11: Acesso por Dispositivo (PC × Celular)
* **PC:** roteador/proxy reverso resolve `https://ROLOX.bass.{username}.{gameid}.com/index.html`, valida o token da sessão e o dispositivo antes de entregar o `index.html`.
  * Nota técnica: nesse formato cada `{gameid}.com` é um domínio registrado, com DNS wildcard e certificado próprios. O `username` já é restrito a caracteres válidos em DNS (ver `perfis`).
* **Celular:** usa o SDK do Supabase direto nas tabelas, protegido pelas políticas RLS da Fase 2.

### Fase 12: Matchmaking Limpo × Hack + Anticheat
* Middleware cruza `perfis.jogo_mod` com `servidores_ativos.is_hack_server`.
* Usuário com hack ativo naquele jogo → só entra em servidor hack (redirecionamento automático).
* Servidores limpos rodam o `rolox-anticheat`; quem for detectado é movido para servidor hack e recebe um aviso.

### Fase 13: Netcode da Partida (Servidor de Jogo)
* Servidor autoritativo em `/game-server` (WebSocket ou UDP) para posição, física e ações em alta frequência.
* Supabase continua com chat, presença, fila e persistência; o servidor de jogo envia o heartbeat para `servidores_ativos`.

### Fase 14: Catálogo de Mapas no GitHub com Aprovação do Dono
* Tabela `jogos` mapeia cada `gameid` ao repositório/branch.
* Nova versão de mapa fica pendente até o dono aprovar; só então `commit_aprovado` e `sha256` são atualizados.
* Backend consulta o GitHub com token próprio (o token nunca vai no cliente) e serve os pacotes via Releases/CDN para evitar o limite da API.

### Fase 15: Downloader e Launcher no PC
* Download com barra de progresso e verificação `sha256`.
* Scripts do mapa rodam em sandbox (sem acesso a arquivos ou rede fora do jogo).
* Ao terminar, abre o jogo com o mapa carregado.

### Fase 16: Chat em Tempo Real (`servidores_logados`)
* Mensagem enviada ao backend → filtrada (Fase 17) → gravada → entregue via Realtime.
* Payload: `username`, `server_uid`, `mensagem_original`, `mensagem_filtrada`, `idioma_original`, `criado_em`.
* Limite de mensagens por segundo por usuário (anti-spam).

### Fase 17: IA SELECT — Tradução e Filtro Contextual
* 1º passo: filtro local por lista de termos (instantâneo).
* 2º passo: IA SELECT só para frases ambíguas e para tradução ao idioma de cada destinatário.
* Cache de traduções repetidas e fallback: se a IA cair ou demorar mais de 1 s, entrega a versão do filtro local.
* `mensagem_original` apagada após 30 dias.

### Fase 18: Streaming Flask (`app.py`)
* Rota `/stream` (MJPEG/WebSocket) exige token válido do Supabase.
* Mostra dados da sessão lidos de `locate_users`.

### Fase 19: Portal da Comunidade e Painel Admin Completo
* Sugestões, reportes de bugs e votação no Supabase; mural público das mais votadas.
* Painel admin ganha: fila de `espera` ao vivo, consumo dos servidores, latência da IA SELECT, reiniciar `server_uid`, logs de auditoria de cada ação de moderador.

### Fase 20: Testes de Carga, Segurança e Deploy Final
* Teste de estresse: Realtime, servidor de jogo, fila, bloqueio de 3 tentativas, download de mapas e latência da IA.
* Revisão final do dono antes de publicar.
* Empacotar o instalador para PC, publicar o app mobile e a documentação oficial no GitHub.

---

## 4. Privacidade (LGPD)
* Política de privacidade explicando IP, alertas de login, localização e chat.
* Localização só com consentimento (`aceitou_localizacao`).
* Retenção: tentativas de login, alertas e `mensagem_original` → 30 dias.
* Usuário pode pedir a exclusão da conta (apaga tudo por `on delete cascade`).

---

## 5. Links e Recursos Oficiais
* **Comunidade Oficial no Discord:** https://discord.gg/Wb39E7vgh
* **Subdomínio PC:** `https://ROLOX.bass.{username}.{gameid}.com/index.html`
