# ROLOX — Base de respostas automáticas do Discord

<!--
COMO O BOT USA ESTE ARQUIVO
- Cada pergunta é um bloco que começa com "### " e vai até o próximo "### " ou "## ".
- A linha "Palavras-chave:" lista os termos que disparam a resposta (separados por vírgula).
- A linha "Comando:" (quando existe) é o comando direto, ex.: !fases.
- O texto depois dessas linhas é a resposta, já no formato do Discord
  (sem tabelas; negrito, listas e blocos de código funcionam).
- Cada resposta tem menos de 2000 caracteres (limite de uma mensagem).
- Atualizado em: 20/11/2026.
-->

## Sobre o Rolox

### O que é o Rolox?
Palavras-chave: rolox, o que é, sobre, jogo, plataforma
Comando: !rolox

🎮 **Rolox** é uma plataforma de jogos feita pela comunidade, com foco em **transparência, segurança e diversão**.

- Jogos criados no **Rolox Studio**, com peças, física e scripts em **Lua (Luau)** e **Python**
- Servidores com **jogadores de IA** que conversam no chat
- **Servidores separados para quem usa hack/mod**, para não atrapalhar quem joga limpo
- **Tickets diários** e **avatar** personalizável
- Chat com **filtro de palavrões**

⚠️ O Rolox está **em teste** e ainda vai ser lançado na Play Store e em outros lugares.

### O Rolox é o Roblox?
Palavras-chave: roblox, é o roblox, cópia, igual roblox, mesmo jogo
Comando: !roblox

Não. O **Rolox** é um projeto **independente**, sem ligação com o Roblox ou com a Roblox Corporation.

As mecânicas são parecidas com as de outros jogos de construção (peças, Workspace, scripts com eventos), mas o código, a plataforma e os jogos são do Rolox.

O Studio consegue **importar modelos `.obj`** que você mesmo exportou de outros editores. Importe só criações **suas** ou que você tem permissão para usar.

### Quando o Rolox vai ser lançado?
Palavras-chave: lançamento, quando lança, data, play store, baixar, download, apk
Comando: !lancamento

📅 Ainda **não há data de lançamento**. O Rolox está em fase de **testes**.

O plano é lançar na **Play Store** e em outros lugares. As novidades saem aqui no Discord primeiro. 👀

Para ver o que já está pronto, use **!fases**.

## Fases do projeto

### Em que fase o Rolox está?
Palavras-chave: fases, fase, progresso, roadmap, andamento, status, o que falta
Comando: !fases

📋 **Fases do Rolox** (20 no total)
✅ pronto · 🟡 em andamento · ⏳ planejado

✅ 2 — Contas e banco de dados (Supabase)
✅ 3 — Login protegido (3 senhas erradas)
✅ 5 — Painel ADM
✅ 6 — Tabelas em tempo real
✅ 7 — Servidores (abrir, fechar, limpar parados)
✅ 8 — Lotação e fila de espera
✅ 9 — Localização (só com permissão)
✅ 10 — Perfil, avatar e config de hack/mod
✅ 16 — Chat dos servidores com filtro
🟡 1 — Estrutura do projeto e testes automáticos
🟡 4 — Recuperação de conta
🟡 11 — Acesso pelo celular ✅ e pelo PC (subdomínios) ⏳
🟡 12 — Servidores limpos × hack ✅ e anticheat ⏳
🟡 14 — Catálogo de mapas pelo GitHub
🟡 17 — IA SELECT: filtro ✅, IAs no chat ✅, tradução ⏳
🟡 19 — Portal da comunidade e painel completo
⏳ 13 — Servidor de jogo (multiplayer em tempo real)
⏳ 15 — Baixar mapas e abrir o jogo no PC
⏳ 18 — Transmissão de tela (Flask)
⏳ 20 — Testes de carga e lançamento

➕ **Extras já prontos:** Rolox Studio (leve e PC), PCtoCelular, tickets, IAs nos servidores e avatar.

Detalhes de cada fase: **!fase** (1 a 10) e **!fase2** (11 a 20).

### O que é cada fase? (detalhes)
Palavras-chave: fase 1, fase 2, fase 3, fase 4, fase 5, fase 6, fase 7, fase 8, fase 9, fase 10, detalhe fase
Comando: !fase

🔎 **Fases 1 a 10**
**1 — Estrutura** 🟡 pastas do projeto e testes; falta testar tudo automaticamente a cada mudança.
**2 — Contas** ✅ login pelo Supabase, perfis e regras de acesso (RLS).
**3 — Login protegido** ✅ 3 senhas erradas bloqueiam o IP de quem errou, e o dono recebe um aviso.
**4 — Recuperar conta** 🟡 a estrutura existe; falta a tela de recuperação.
**5 — Painel ADM** ✅ tickets, banir/desbanir, IPs bloqueados, servidores.
**6 — Tempo real** ✅ tabelas de servidores, jogadores, fila, localização e chat.
**7 — Servidores** ✅ quem cria vira o dono; os parados são removidos sozinhos.
**8 — Fila** ✅ servidor cheio = fila; quando alguém sai, o próximo entra.
**9 — Localização** ✅ mostra onde você está (menu, lobby, jogo) só se você permitir.
**10 — Perfil** ✅ idioma, avatar, e-mail opcional e jogo com hack/mod.

Fases 11 a 20: **!fase2**

### O que é cada fase? (11 a 20)
Palavras-chave: fase 11, fase 12, fase 13, fase 14, fase 15, fase 16, fase 17, fase 18, fase 19, fase 20
Comando: !fase2

🔎 **Fases 11 a 20**
**11 — Acesso** 🟡 celular pronto; endereço próprio para cada jogo no PC ainda não.
**12 — Hack × limpo** 🟡 a separação de servidores funciona; o anticheat ainda não.
**13 — Servidor de jogo** ⏳ multiplayer de verdade, com posição e física em tempo real.
**14 — Mapas no GitHub** 🟡 o catálogo existe e só mostra jogos aprovados; falta a ligação automática com o GitHub.
**15 — Launcher do PC** ⏳ baixar o mapa, conferir e abrir o jogo.
**16 — Chat** ✅ mensagens com filtro e limite de spam.
**17 — IA SELECT** 🟡 filtro e IAs no chat prontos; falta traduzir mensagens.
**18 — Transmissão** ⏳ ver a tela do jogo em outro aparelho.
**19 — Comunidade** 🟡 painel ADM pronto; falta o mural de sugestões e votação.
**20 — Lançamento** ⏳ testes de carga, revisão final e publicação.

## App e conta

### Como instalar/abrir o app?
Palavras-chave: instalar, como abrir, rodar, termux, flet, iniciar app, abrir app
Comando: !instalar

📲 **App Rolox (teste) no Termux**
```
pkg install python git
git clone -b claude/rolox-arquitetura-v2-review-n5kxxe https://github.com/a30208777-ai/Claude-code-data1
cd Claude-code-data1/Rolox-App/mobile
pip install "flet[web]==1.1.2"
flet run --web --port 8550 src/main.py
```
Depois abra **http://127.0.0.1:8550** no navegador do celular.

Se der erro no `pip`, veja **!erro pydantic**. Também existe uma versão em **Flask**, mais leve: **!flask**.

### Versão Flask (mais leve)
Palavras-chave: flask, versão leve, sem flet, não instala flet
Comando: !flask

🪶 **App Rolox em Flask**: só precisa de `flask` e `requests`, sem compilar nada.
```
cd Claude-code-data1/Rolox-App/flask
pip install flask requests
python app.py
```
Abra **http://localhost:8550** no navegador.

Dica: no menu do Chrome, **"Adicionar à tela inicial"** faz ele abrir como um app.

### Como criar conta? Precisa de e-mail?
Palavras-chave: criar conta, cadastro, registrar, e-mail, email, confirmar email
Comando: !conta

👤 Para criar a conta, só precisa de **usuário e senha**.
- Usuário: 3 a 32 letras **minúsculas**, números ou hífen (sem hífen no começo nem no fim)
- Senha: no mínimo 8 caracteres
- Depois de cadastrar, você já entra direto

📧 O **e-mail é opcional**: dá para adicionar depois em **Perfil**. Ele serve para contato e recuperação.

### Errei a senha / meu IP foi bloqueado
Palavras-chave: senha errada, bloqueado, ip bloqueado, 3 tentativas, não consigo entrar, banido ip
Comando: !senha

🔒 **Proteção do login**
- **3 senhas erradas** do mesmo aparelho na mesma conta bloqueiam o **IP de quem errou**
- A **conta não é banida**: o dono recebe um aviso no app (*"Alguém tentou entrar na sua conta"*), com o IP e a senha que foi tentada
- Se quem errou foi **o próprio dono**, no aparelho de sempre, o IP **não** é bloqueado: se a conta tem e-mail, chega um e-mail para trocar a senha; se não tem, aparece "Muitas senhas erradas, espere um pouco"

Se o seu IP foi bloqueado por engano, fale com um **ADM** aqui no Discord.

### Alguém tentou entrar na minha conta!
Palavras-chave: alerta, tentaram entrar, invadir, hack conta, alguém tentou
Comando: !alerta

🛡️ Os **Alertas de segurança** ficam na tela **Início** do app.
- Cada alerta mostra o **IP**, a **data** e se o IP foi **banido**
- No 👁️ você vê **qual senha a pessoa tentou**. Só o dono da conta consegue ver
- A senha tentada fica guardada **criptografada** e é apagada em 30 dias

💡 Se a senha tentada for parecida com a sua, **troque de senha**.

## Tickets, IAs e avatar

### O que são tickets?
Palavras-chave: ticket, tickets, moeda, presente diário, ganhar tickets
Comando: !tickets

🎟️ **Tickets**
- **1 ticket = R$ 0**: não é dinheiro e não se compra
- **1 ticket = 1 resposta de IA** no chat dos servidores
- **Presente diário:** ao abrir o app você ganha tickets, e o presente **dobra a cada dia**: 5 → 10 → 20 → 40 → 80 → 160 → 320 → **640** (o máximo por dia)
- Sem tickets, as IAs **não respondem** às suas mensagens
- Se a IA falhar, o ticket **volta**

👑 **ADMs** têm tickets infinitos (∞).

### O que são as IAs nos servidores?
Palavras-chave: ia, ias, bot, bots, jogadores ia, inteligência artificial, quem é lia, zeca, duda
Comando: !ias

🤖 **Jogadores de IA**
- Todo servidor ganha IAs: **metade da capacidade, arredondada para baixo** (10 vagas → 5 IAs, 11 → 5, 3 → 1)
- **Jogadores reais têm prioridade:** se o servidor enche, uma IA sai para dar a vaga
- Cada IA tem nome e jeito próprio (Lia, Teco, Duda, Rafa, Zeca, Mel…)
- Elas respondem quando são **chamadas pelo nome** ou quando alguém fala com o grupo ("oi pessoal", perguntas)
- As mensagens delas têm a etiqueta **IA**, e se você perguntar, **elas dizem que são IA**
- Cada resposta usa **1 ticket** de quem mandou a mensagem (**!tickets**)

### Como mudar meu avatar?
Palavras-chave: avatar, personagem, roupa, skin, cabelo, mudar visual
Comando: !avatar

🧍 No app, vá em **Perfil → Avatar** e escolha:
- **Pele**
- **Cabelo:** curto, longo, moicano, topete ou careca
- **Cor do cabelo**, **camisa** e **calça**
- **Acessório:** óculos, boné, coroa ou fone

A prévia muda na hora. Toque em **Salvar**. Este é o **primeiro passo** dos avatares; mais opções vão chegar. ✨

## Servidores e regras

### Posso usar hack/mod?
Palavras-chave: hack, mod, mods, trapaça, cheat, servidor hack, usar hack
Comando: !hack

🧪 **Pode, mas só nos servidores de hack/mod.**
1. No app, vá em **Perfil → "Jogo onde uso hack/mod"** e escolha o jogo
2. Para esse jogo, você só entra em servidores com a etiqueta **HACK/MOD**
3. Quem joga limpo **não entra** nos servidores de hack, e vice-versa

🔄 Trocou de ideia? Mude no Perfil a qualquer momento. Se trocar no meio de uma partida, você sai daquele servidor.

⚠️ Usar hack em **servidor limpo** é contra as regras (o anticheat está a caminho).

### Servidor cheio / fila de espera
Palavras-chave: servidor cheio, fila, espera, não consigo entrar no servidor, lotado
Comando: !fila

⏳ Se o servidor está **cheio de jogadores reais**, você entra na **fila de espera**.
- A tela **Início** mostra a sua **posição na fila**
- Quando alguém sai, o **primeiro da fila entra sozinho**
- Você só fica em **um servidor ou fila por vez**

Dica: as **IAs não contam como vaga ocupada** para jogadores reais. Elas saem para você entrar.

### Regras do chat
Palavras-chave: chat, palavrão, filtro, xingar, spam, mensagem apagada
Comando: !chat

💬 **Chat dos servidores**
- **Filtro de palavrões:** o palavrão é tirado e o resto da frase continua (ex.: "achei um cão mais era **a p\*\*\*\* de** uma sacola" → "achei um cão mais era uma sacola")
- **Anti-spam:** no máximo 1 mensagem por segundo
- Mensagens de até 500 caracteres
- Seja gentil: ofensas podem dar **ban** pelos ADMs

## Rolox Studio (criar jogos)

### O que é o Rolox Studio?
Palavras-chave: studio, criar jogo, editor, fazer jogo, rolox studio
Comando: !studio

🛠️ O **Rolox Studio** é o editor de jogos do Rolox. Roda no navegador e tem **2 versões**:
- 📱 **Studio leve** (celular): gráficos simples, interface de toque, arrastar peças com o dedo, até 400 peças
- 🖥️ **Studio PC**: sombras, setas para mover e escalar, painéis lado a lado e **PCtoCelular**, até 5000 peças

Dá para: criar peças, testar com **▶ Jogar**, salvar e abrir projetos, **desfazer/refazer** (Ctrl+Z/Ctrl+Y), importar **.obj** e começar com modelos prontos (**Obby** e **Coleta de moedas**).

Como abrir: **!studio abrir**

### Como abrir o Studio?
Palavras-chave: abrir studio, ligar studio, studio desligado, rodar studio
Comando: !studio abrir

▶️ **Ligar o Studio (Termux ou PC)**
```
cd Claude-code-data1/Rolox-Studio
pip install -r requirements.txt
python servidor.py
```
Abra **http://localhost:8600** e escolha **Studio leve** ou **Studio PC**.

📲 Também dá para abrir pela aba **Studio** do app. No Termux, use **duas sessões**: uma com o Studio e outra com o app.

Sem internet? Rode uma vez `python baixar_pyodide.py` para os scripts em Python funcionarem offline.

### Que linguagem uso nos scripts?
Palavras-chave: linguagem, lua, luau, python, script, localscript, modulescript, programar
Comando: !scripts

📜 **Scripts no Rolox Studio**
- **LocalScript** (roda no aparelho do jogador): **Lua/Luau**
- **Script** (servidor): **Python**
- **ModuleScript**: **Lua ou Python**, quem decide é o dono do jogo

A linguagem fica na **primeira linha** do script:
```
_++linguagemprogroma++_ = lua
_++linguagemprogroma++_ = python
```
⚠️ Dá para usar Python num LocalScript, mas o Studio avisa: o jogador precisaria rodar Python no celular pelo **Termux**, e isso pode **afastar jogadores**.

Exemplos: **!lua** e **!python**

### Exemplo de script em Lua (Luau)
Palavras-chave: exemplo lua, lua exemplo, luau exemplo, como programar lua
Comando: !lua

🌙 **Lava que mata (LocalScript)**
```lua
_++linguagemprogroma++_ = lua
local tempo: number = 0
workspace.Lava.Touched:Connect(function(outro)
  local hum = outro.Parent:FindFirstChildOfClass("Humanoid")
  if hum then hum.Health = 0 end
end)
game:GetService("RunService").Heartbeat:Connect(function(dt)
  tempo += dt
end)
wait(5)
print(`Já se passaram {math.floor(tempo)} segundos`)
```
Funciona no Luau: tipos (`: number`), `+=`, `` `texto {valor}` ``, `continue` e `type`.

### Exemplo de script em Python
Palavras-chave: exemplo python, python exemplo, como programar python, server script
Comando: !python

🐍 **Moeda que some e volta (Script do servidor)**
```python
_++linguagemprogroma++_ = python
moeda = workspace.Moeda

async def pegou(outro):
    if outro.Parent.FindFirstChildOfClass("Humanoid"):
        moeda.Transparency = 1
        await wait(5)
        moeda.Transparency = 0

moeda.Touched.Connect(pegou)
moeda.Position = moeda.Position + Vector3.new(0, 1, 0)
```
No Python, use `await wait(...)` para esperar. `Vector3` funciona com `+ - * /`.

### Como importar um modelo .obj?
Palavras-chave: obj, importar, modelo 3d, exportar, mtl, malha, mesh
Comando: !obj

📦 **Importar .obj no Rolox Studio**
1. No editor de origem, exporte o modelo como **.obj** (junto saem o **.mtl** e as texturas **.png**)
2. No Rolox Studio, clique em **Importar .obj**
3. Selecione **todos os arquivos juntos** (.obj + .mtl + .png)
4. O modelo vira um **MeshPart** com o tamanho real e fica salvo no projeto

Limites: .obj até 30 MB e cada textura até 4 MB.
⚠️ Importe só modelos que **você criou** ou que tem permissão para usar.

### O que é o PCtoCelular?
Palavras-chave: pctocelular, pc to celular, celular controle, controle, bluetooth, cabo, sensor
Comando: !pctocelular

🎮 **PCtoCelular**: o celular vira **controle** do jogo no PC.
- **Incline** o celular para o personagem andar e **levante rápido** para pular
- Até **5 celulares por Bluetooth** e **2 por cabo**, e cada um vira um jogador
- Os dados do sensor ficam **só entre o celular e o PC**, sem ir para a internet
- Se o celular não tiver sensor, vira um **joystick** na tela
- Quem joga **pelo celular** não vê essa mecânica

**Por cabo:** ligue a depuração USB, rode `adb reverse tcp:8600 tcp:8600` no PC e abra `http://localhost:8600/controle` no celular.
**Por Bluetooth:** ative a ancoragem Bluetooth no celular, rode o Studio com `ROLOX_HOST=0.0.0.0` e abra `http://IP-DO-PC:8600/controle`.
Digite o **código de 4 dígitos** que aparece no Studio PC.

## Erros comuns

### Erro: Failed to build pydantic-core
Palavras-chave: pydantic, pydantic-core, failed to build, erro pip, rust, não instala
Comando: !erro pydantic

🧰 O pacote `flet[web]` precisa compilar o `pydantic-core` (feito em Rust), e o Termux não tem o Rust pronto.

**Solução:**
```
pkg update
pkg install rust binutils clang make
export ANDROID_API_LEVEL=$(getprop ro.build.version.sdk)
pip install "flet[web]==1.1.2"
```
⏱️ Pode levar de 10 a 30 minutos: deixe o celular carregando.

**Alternativa sem compilar:** use a versão **Flask** (**!flask**).

### Erro: NOT_FOUND ao entrar
Palavras-chave: not_found, not found, erro not found, servidor não configurado
Comando: !erro notfound

❓ Significa que o app não achou a função de login no servidor. Geralmente o **app está desatualizado** e aponta para um servidor antigo.

**Solução:** atualize o app:
```
cd Claude-code-data1
git pull
```
e rode o app de novo. Se continuar, avise um **ADM**.

### Erro: cadastrar() missing argument / arquivos misturados
Palavras-chave: missing, argument, missing 1 required, cadastrar, aceitou_localizacao, typeerror, attributeerror
Comando: !erro versao

🧩 Esse erro aparece quando **uma parte do app é nova e outra é antiga**, por exemplo trocar só o `telas.py` sem trocar o `api.py`.

**Solução:** atualize tudo de uma vez:
```
cd Claude-code-data1
git checkout -- .
git pull
```
⚠️ O `git checkout -- .` desfaz arquivos trocados à mão. Depois, rode o app de novo.

### Erro: flet: command not found
Palavras-chave: command not found, flet não encontrado, flet não existe
Comando: !erro flet

🔧 Rode o Flet pelo Python:
```
python -m flet run --web --port 8550 src/main.py
```
Se der `No module named flet`, instale antes: **!instalar**.

### Porta em uso / Address already in use
Palavras-chave: porta em uso, address already in use, 8550, 8600, já está rodando
Comando: !erro porta

🚪 Já tem algo rodando nessa porta, provavelmente o app ou o Studio aberto em outra sessão do Termux.
- Volte na outra sessão e aperte **Ctrl + C** (o Ctrl fica na barra de teclas extras do Termux)
- Ou use outra porta: `--port 8551` (app) ou `ROLOX_PORTA=8601 python servidor.py` (Studio)

### O app diz "Studio desligado"
Palavras-chave: studio desligado, studio não liga, aba studio
Comando: !erro studio

🛠️ A aba **Studio** do app procura o Rolox Studio **no mesmo aparelho**.
1. No Termux, abra uma **nova sessão** (deslize da esquerda e toque em **NEW SESSION**)
2. Rode:
```
cd Claude-code-data1/Rolox-Studio && python servidor.py
```
3. Volte ao app e toque em **Tentar de novo**

## Privacidade e segurança

### Quais dados o Rolox guarda?
Palavras-chave: privacidade, dados, lgpd, meus dados, apagar conta, localização
Comando: !privacidade

🔐 **Privacidade (LGPD)**
- **Localização no Rolox** (menu, lobby, jogo): só com a sua **permissão**, e dá para desligar no Perfil
- **E-mail:** opcional
- **Tentativas de login e alertas:** apagados em **30 dias**
- **Senhas tentadas:** guardadas **criptografadas**
- **Chat:** a mensagem original é apagada em 30 dias (fica só a versão filtrada)
- **PCtoCelular:** os dados do sensor **não saem** do seu celular e do seu PC

Para apagar sua conta, fale com um **ADM**.

### Como reportar bug ou dar sugestão?
Palavras-chave: bug, erro, sugestão, ideia, reportar, feedback, problema
Comando: !bug

🐞 Encontrou um bug ou tem uma ideia? Mande aqui no Discord, no canal de bugs ou sugestões, com:
- o que você fez
- o que aconteceu (print ajuda muito 📸)
- o que deveria acontecer
- celular ou PC, e qual versão (app Flet, Flask ou Studio)

O **mural de sugestões com votação** vai chegar no app (fase 19).

## Links

### Links oficiais
Palavras-chave: links, discord, github, convite
Comando: !links

🔗 **Links oficiais do Rolox**
- Discord: https://discord.gg/Wb39E7vgh
- Código (teste): https://github.com/a30208777-ai/Claude-code-data1

⚠️ Nunca passe sua senha para ninguém, nem para quem diz ser ADM. **A equipe do Rolox nunca pede senha.**
