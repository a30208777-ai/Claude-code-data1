# Bot do Discord + Painel Web

Bot do Discord em Python com um **painel no navegador** para ler e escrever nos canais onde o bot tem acesso. Assim, quem não consegue instalar o Discord também participa. O acesso ao painel é protegido por senha.

- **Hospedagem:** Render (Web Service)
- **Banco de dados:** Supabase, que guarda o histórico de logins e das mensagens enviadas pelo painel
- **Código:** GitHub

## Arquivos

| Arquivo | O que é |
|---|---|
| `bot.py` | Bot + servidor web (login, canais, mensagens, envio e tempo real) |
| `static/index.html` | O painel que abre no navegador |
| `requirements.txt` | Bibliotecas Python |
| `../render.yaml` | Configuração pronta para o Render (fica na raiz do repositório) |
| `supabase.sql` | Tabelas para criar no Supabase |
| `.env.example` | Modelo das variáveis (só para testar no PC) |

## Passo a passo

### 1. Discord: criar o bot
1. Acesse <https://discord.com/developers/applications> → **New Application**.
2. Aba **Bot** → **Reset Token** → copie o token. Esse é o `DISCORD_BOT_TOKEN`; ele só aparece uma vez.
3. Ainda na aba **Bot**, ative **MESSAGE CONTENT INTENT**. Sem isso, as mensagens aparecem vazias.
4. Aba **OAuth2 → URL Generator**: marque `bot` e `applications.commands`. Nas permissões, marque:
   View Channels, Send Messages, Read Message History, Attach Files, Embed Links e **Manage Webhooks**.
5. Abra o link gerado e adicione o bot ao seu servidor.

> A permissão **Manage Webhooks** faz a mensagem aparecer com o nome de quem escreveu, por exemplo "João (via painel)". Sem ela, a mensagem sai como o bot, com o nome na frente.
>
> O bot só enxerga os canais onde tem permissão. Para esconder um canal do painel, tire do bot a permissão de ver esse canal.

### 2. Supabase: criar as tabelas
1. Abra o projeto no <https://supabase.com> → **SQL Editor** → **New query**.
2. Cole o conteúdo de `supabase.sql` e clique em **Run**.
3. Em **Project Settings → API**, copie a **Project URL** (`SUPABASE_URL`) e a chave **service_role** (`SUPABASE_SERVICE_ROLE_KEY`).

> A chave service_role é secreta. Ela fica só no Render, nunca no HTML nem no GitHub.
> O Supabase é opcional: sem essas duas variáveis, o bot funciona normalmente, só não guarda o histórico.

### 3. GitHub: subir o código
Envie todos os arquivos para um repositório. O `.gitignore` já impede que o `.env` seja enviado.

### 4. Render: colocar no ar
1. Em <https://dashboard.render.com>, clique em **New → Blueprint**, escolha o repositório `claude-code-data1` e o branch `ccr-2b660cd9-dhk43n`. O Render lê o `render.yaml` da raiz, que aponta para a pasta `discord-bot-painel`.
2. Preencha as variáveis que ele pedir:

| Variável | Valor |
|---|---|
| `DISCORD_BOT_TOKEN` | token do passo 1 |
| `PANEL_PASSWORD` | **a senha do painel** (ex.: `lobinho123`, mas prefira uma mais forte) |
| `SECRET_KEY` | gerada sozinha pelo Render |
| `SUPABASE_URL` | do passo 2 |
| `SUPABASE_SERVICE_ROLE_KEY` | do passo 2 |

3. Clique em **Apply**. Quando terminar, o painel fica em `https://discord-bot-painel.onrender.com`; o endereço exato aparece no topo do serviço.

Para **trocar a senha**, mude `PANEL_PASSWORD` em **Environment** no Render e salve. Todo mundo é desconectado e precisa entrar com a senha nova.

## Como usar
- Abra o link do painel, digite **seu nome** (é o que aparece no Discord) e a **senha**.
- Escolha o servidor e o canal. As mensagens chegam em tempo real.
- No campo de mensagem: **Enter** envia e **Shift+Enter** pula linha. O **＋** anexa uma imagem ou arquivo (até 8 MB) e o **↩** responde a uma mensagem.
- Canais com 🔒 são somente leitura, porque o bot não pode escrever neles.
- No Discord: `/ping`, `/painel` (mostra o link do painel) e `/ajuda`.

## Plano grátis do Render
No plano **Free**, o serviço **dorme depois de 15 min sem ninguém abrir o painel**, e o bot fica offline enquanto isso. Quando alguém abre o link, ele acorda em cerca de 1 minuto.
Para o bot ficar online 24h, use o plano **Starter** do Render ou um serviço de "ping" (ex.: UptimeRobot) chamando `https://SEU-APP.onrender.com/health` a cada 10 minutos.

## Segurança
- A senha é conferida só no servidor e nunca aparece no HTML.
- O login fica salvo por 30 dias num cookie assinado (HttpOnly).
- Depois de 5 senhas erradas, o IP fica bloqueado por 15 minutos.
- Cada pessoa pode enviar no máximo 5 mensagens a cada 5 segundos.
- Mensagens do painel **não marcam** @everyone, @here nem pessoas.

## Testar no seu PC (opcional)
```bash
pip install -r requirements.txt
cp .env.example .env   # preencha os valores
set -a; source .env; set +a
python bot.py          # abra http://localhost:10000
```
