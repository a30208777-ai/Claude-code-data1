# ROLOX — Arquitetura Técnica, Plano Completo (20 Fases) e Diretrizes

Este documento reúne todas as especificações, prioridades e o plano de execução detalhado dividido em **20 fases sequenciais** (`H1`, `H2`, etc.) para o desenvolvimento completo da plataforma **Rolox** — uma alternativa aprimorada ao Roblox para PC, focada em comunidade, transparência, segurança, servidores customizados e sincronização em tempo real.

---

## H1 — Visão Geral e Prioridades do Projeto (Classificação 1 a 10)

### H2 — 1. Banco de Dados Unificado e Autenticação Blindada (Supabase) — Nota: 10/10
* Centralização total do banco de dados no **Supabase** (substituindo o antigo plano com MongoDB Atlas).
* Tabela `usuarios` contendo: `id`, `username`, `senha_hash`, `ip`, `tentativas_falhas`, `banido`, `token_desafio`, `credencial_backup` e `ips_bloqueados`.
* **Política de Bloqueio:** 3 tentativas falhas de login resultam no banimento automático da conta e bloqueio permanente do IP.

### H2 — 2. Sincronização em Tempo Real (Supabase - 5 Tabelas) — Nota: 10/10
* Gerenciamento de estado e comunicação em tempo real entre dispositivos através de 5 tabelas principais:
  * `servidores_logados`: Chats, usernames e itens ativos da sessão.
  * `servidores_ativos`: Relaciona `server-uid` e `user`.
  * `users_dos_servidores`: Mapeia quais usuários estão em cada servidor (`user`, `server-uid`).
  * `locate_users`: Rastreia a localização atual dos usuários na plataforma (`locate`, `user`).
  * `espera`: Fila de usuários aguardando vaga para entrar em servidores cheios.

### H2 — 3. IA Tradutora e Moderação Contextual ("SELECT") — Nota: 9/10
* Inteligência artificial embutida no chat que traduz mensagens em tempo real e filtra termos impróprios de forma contextual, preservando o sentido útil da frase (ex.: *"hj eu achei um cão mais era a porra de uma sacola"* vira *"hj eu achei um cão mais era uma sacola"*).

### H2 — 4. Servidores Separados para Hacks e Mods — Nota: 9/10
* Uso de hacks e mods é permitido, mas isolado em **servidores dedicados** para não prejudicar jogadores comuns.
* Gerenciado diretamente na **Tela de Perfil** (seleção do jogo onde o hack será usado) com opção de alteração rápida no menu `config`.

### H2 — 5. Hospedagem e Carregamento de Mapas via GitHub — Nota: 8/10
* Todos os mapas ficam versionados e hospedados em repositórios no GitHub.
* O cliente PC baixa o mapa correspondente e inicia o jogo localmente assim que o download é concluído.

### H2 — 6. Subdomínios Dinâmicos para Sessões (PC) — Nota: 8/10
* Estrutura de roteamento isolado no formato:
  `https://ROLOX.bass.{username}.{gameid}.com/index.html`

### H2 — 7. Tela de Perfil e Gestão de Jogos/Mods — Nota: 7/10
* Interface onde o usuário visualiza e define em qual jogo está utilizando mods/hacks, com correção rápida no menu de configurações.

### H2 — 8. Módulo de Transmissão de Tela via Flask (Python) — Nota: 7/10
* Servidor leve em Python + Flask (`app.py`) para transmissão remota de frames/tela e testes em dispositivos móveis (Termux).

---

## H1 — Plano de Execução Completo para o Claude Code (Fases 1 a 20)

### H2 — Fase 1: Inicialização do Repositório e Estrutura Base
* **Objetivo:** Preparar a arquitetura de pastas, gerenciador de pacotes e variáveis de ambiente (`.env`).
* **Tarefas:**
  1. Criar diretórios separados para `/backend`, `/client-pc`, `/streaming-flask`, `/database-sql` e `/docs`.
  2. Configurar `.env.example` com chaves do Supabase, GitHub API e segredos JWT.

### H2 — Fase 2: Schema de Autenticação e Segurança no Supabase
* **Objetivo:** Estruturar a tabela principal de usuários e políticas de proteção.
* **Tarefas:**
  1. Criar o script SQL da tabela `usuarios` (`id`, `username`, `senha_hash`, `ip`, `tentativas_falhas`, `banido`, `token_desafio`, `credencial_backup`, `ips_bloqueados`).
  2. Configurar índices únicos para `username` e regras de Row Level Security (RLS).

### H2 — Fase 3: Motor de Login Blindado e Bloqueio Automático (3 Tentativas)
* **Objetivo:** Implementar o sistema de autenticação com banimento automático contra força bruta.
* **Tarefas:**
  1. Criar endpoint `/auth/login` verificando hash de senha (Argon2/Bcrypt) e checando se o IP já está em `ips_bloqueados`.
  2. Incrementar `tentativas_falhas` a cada erro e, ao atingir **3 falhas**, setar `banido = true` e gravar o IP na lista negra.

### H2 — Fase 4: Recuperação de Conta e Tokens de Desafio
* **Objetivo:** Permitir recuperação segura e validação de sessão via `token_desafio` e `credencial_backup`.
* **Tarefas:**
  1. Criar fluxo de geração e validação de tokens de sessão.
  2. Implementar endpoint seguro para desbloqueio administrativo ou via credencial de backup.

### H2 — Fase 5: Criação das 5 Tabelas de Tempo Real no Supabase
* **Objetivo:** Estruturar toda a base de sincronização multiplayer e filas.
* **Tarefas:**
  1. Gerar SQL e criar as tabelas: `servidores_logados`, `servidores_ativos`, `users_dos_servidores`, `locate_users` e `espera`.
  2. Habilitar o **Supabase Realtime** em todas as 5 tabelas para broadcast instantâneo.

### H2 — Fase 6: Gerenciador de Servidores Ativos (`servidores_ativos`)
* **Objetivo:** Controlar a abertura, registro e encerramento de instâncias de jogo.
* **Tarefas:**
  1. Criar lógica para registrar um novo `server-uid` atrelado ao host/usuário criador.
  2. Implementar rotina de limpeza automática (heartbeat) para remover servidores inativos ou vazios.

### H2 — Fase 7: Alocação de Jogadores e Fila de Espera (`users_dos_servidores` e `espera`)
* **Objetivo:** Gerenciar lotação de salas e entrada ordenada quando houver vagas.
* **Tarefas:**
  1. Verificar capacidade máxima do servidor antes de inserir na tabela `users_dos_servidores`.
  2. Caso o servidor esteja cheio, inserir o jogador automaticamente na tabela `espera` e notificá-lo via Realtime assim que uma vaga abrir.

### H2 — Fase 8: Rastreamento de Localização Cross-Device (`locate_users`)
* **Objetivo:** Sincronizar em tempo real onde o usuário está (Menu, Lobby, Jogo X, Modo Hack) entre dispositivos.
* **Tarefas:**
  1. Atualizar a tabela `locate_users` (`locate`, `user`) a cada mudança de estado do cliente.
  2. Exibir status online e localização atual para amigos e painel administrativo.

### H2 — Fase 9: Tela de Perfil e Seletor de Jogos com Hack/Mod
* **Objetivo:** Dar transparência e controle sobre quais jogos o usuário pretende usar modificações.
* **Tarefas:**
  1. Criar estrutura de perfil listando todos os jogos disponíveis na plataforma.
  2. Salvar no Supabase a marcação de qual jogo o usuário ativou o modo Hack/Mod.

### H2 — Fase 10: Menu de Configurações (`config`) para Troca Rápida
* **Objetivo:** Permitir correção imediata caso o usuário marque o jogo errado no perfil.
* **Tarefas:**
  1. Criar interface e rota API `/profile/config/mod-game` para alterar ou desativar a seleção de hack a qualquer momento.
  2. Forçar desconexão limpa caso o usuário mude o status no meio de uma partida incompatível.

### H2 — Fase 11: Roteamento de Subdomínios Dinâmicos para PC
* **Objetivo:** Implementar a arquitetura de URLs isoladas exclusivas para computadores.
* **Tarefas:**
  1. Configurar proxy reverso / roteador para resolver o padrão `https://ROLOX.bass.{username}.{gameid}.com/index.html`.
  2. Validar assinatura da sessão e dispositivo PC antes de entregar o `index.html` da instância.

### H2 — Fase 12: Matchmaking Separado (Servidores Limpos vs. Servidores Hack)
* **Objetivo:** Garantir isolamento absoluto entre jogadores comuns e usuários de mods/hacks.
* **Tarefas:**
  1. Criar middleware de entrada que cruza o status do perfil do usuário com a flag do servidor (`is_hack_server`).
  2. Bloquear entrada de usuários marcados com hack em servidores limpos e redirecioná-los automaticamente para servidores separados de hack.

### H2 — Fase 13: Integração com GitHub para Repositório de Mapas
* **Objetivo:** Conectar a plataforma aos repositórios do GitHub onde os mapas ficam armazenados.
* **Tarefas:**
  1. Criar catálogo mapeando cada `gameid` ao seu respectivo repositório/branch no GitHub.
  2. Implementar verificação de versão/commit hash para detectar atualizações de mapas automaticamente.

### H2 — Fase 14: Downloader Local e Launcher Automático no Cliente PC
* **Objetivo:** Baixar o mapa do GitHub no PC do jogador e abrir o jogo assim que o download terminar.
* **Tarefas:**
  1. Desenvolver módulo de download com barra de progresso e verificação de integridade (checksum).
  2. Disparar automaticamente a execução do cliente/engine do jogo carregando o mapa recém-baixado.

### H2 — Fase 15: Pipeline de Chat em Tempo Real (`servidores_logados`)
* **Objetivo:** Construir a infraestrutura de envio e recebimento de mensagens dentro dos servidores.
* **Tarefas:**
  1. Conectar o chat do jogo à tabela `servidores_logados` via Supabase Realtime.
  2. Estruturar payload contendo `username`, `server-uid`, `mensagem_original`, `mensagem_filtrada` e `timestamp`.

### H2 — Fase 16: Integração da IA Tradutora e Filtro Contextual ("SELECT")
* **Objetivo:** Traduzir idiomas simultaneamente e limpar palavrões sem destruir o contexto da frase.
* **Tarefas:**
  1. Criar serviço intermediário que envia cada mensagem para a IA **SELECT** antes da entrega.
  2. Aplicar prompt de sanitização contextual (ex.: remover apenas termos ofensivos mantendo o sentido útil da frase) e tradução para o idioma do destinatário.

### H2 — Fase 17: Servidor de Streaming Remoto em Flask (`app.py`)
* **Objetivo:** Disponibilizar transmissão de tela/frames leve para testes mobile e Termux.
* **Tarefas:**
  1. Estruturar o micro-servidor Python com Flask (`app.py`) e rota MJPEG/WebSocket `/stream`.
  2. Integrar leitura de status com `locate_users` no Supabase para exibir dados da sessão na tela de transmissão.

### H2 — Fase 18: Portal de Feedback e Votação da Comunidade
* **Objetivo:** Cumprir o pilar central do Rolox de sempre ouvir a comunidade.
* **Tarefas:**
  1. Criar sistema de envio de sugestões, reportes de bugs e votação de recursos diretamente conectado ao Supabase.
  2. Exibir mural público com as ideias mais votadas pelos jogadores.

### H2 — Fase 19: Painel Administrativo, Logs de Segurança e Auditoria
* **Objetivo:** Monitorar tentativas de invasão, IPs banidos, servidores ativos e desempenho da IA SELECT.
* **Tarefas:**
  1. Criar dashboard restrito exibindo contas banidas, fila de `espera` em tempo real e consumo dos servidores.
  2. Adicionar ferramentas de moderação manual (banir/desbanir IP, reiniciar `server-uid`).

### H2 — Fase 20: Testes de Carga, Segurança e Deploy Final
* **Objetivo:** Validar toda a plataforma antes do lançamento oficial para a comunidade.
* **Tarefas:**
  1. Executar testes automatizados de estresse no Supabase Realtime, bloqueio de 3 tentativas, download de mapas no GitHub e latência da IA SELECT.
  2. Empacotar o instalador final para PC e publicar a documentação oficial no GitHub.

---

## H1 — Links e Recursos Oficiais

* **Comunidade Oficial no Discord:** https://discord.gg/Wb39E7vgh
* **Estrutura de Subdomínio:** `https://ROLOX.bass.{username}.{gameid}.com/index.html`
