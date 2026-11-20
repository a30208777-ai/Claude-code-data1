# ROLOX — Respostas automáticas (Discord)
<!-- Cada "###" é uma resposta. Linha "Palavras:" = gatilhos. Atualizado 20/11/2026. -->

### !rolox
Palavras: rolox, o que é, roblox
🎮 Plataforma de jogos da comunidade: Studio para criar jogos (Lua e Python), IAs no chat, servidores separados para hack/mod, tickets e avatar. É **independente** (não é o Roblox) e está **em teste**, sem data de lançamento.

### !fases
Palavras: fase, fases, progresso, roadmap, falta
✅ Contas, login protegido, painel ADM, tempo real, servidores, fila, localização, perfil/avatar, chat
🟡 Recuperar conta, acesso pelo PC, anticheat, mapas no GitHub, tradução no chat, mural de sugestões
⏳ Multiplayer em tempo real, launcher do PC, transmissão de tela, lançamento
➕ Prontos: Rolox Studio, PCtoCelular, tickets, IAs

### !instalar
Palavras: instalar, abrir app, termux, flet
```
pkg install python git
git clone -b claude/rolox-arquitetura-v2-review-n5kxxe https://github.com/a30208777-ai/Claude-code-data1
cd Claude-code-data1/Rolox-App/mobile
pip install "flet[web]==1.1.2"
flet run --web --port 8550 src/main.py
```
Abra http://127.0.0.1:8550. Mais leve: em `Rolox-App/flask` rode `pip install flask requests` e `python app.py`.

### !conta
Palavras: criar conta, cadastro, email
Só **usuário** (3 a 32 minúsculas, números ou hífen) e **senha** (8+). O e-mail é opcional, em Perfil.

### !senha
Palavras: senha errada, bloqueado, ip, alguém tentou
3 senhas erradas bloqueiam o **IP de quem errou**, não a conta. O dono vê o alerta no Início (IP e senha tentada). Bloqueado por engano? Chame um ADM.

### !tickets
Palavras: ticket, tickets, presente
1 ticket = R$ 0 = 1 resposta de IA. O presente diário dobra: 5→10→20…→640 por dia. Sem tickets, as IAs não respondem. ADM tem ∞.

### !ias
Palavras: ia, ias, bot, lia, zeca
Cada servidor tem IAs: metade da capacidade, para baixo (10→5, 11→5). Jogadores reais têm prioridade. Elas respondem quando chamadas pelo nome ou com "oi pessoal", têm a etiqueta **IA** e dizem que são IA.

### !hack
Palavras: hack, mod, cheat
Pode, só nos servidores **HACK/MOD**: marque o jogo em Perfil. Hack em servidor limpo = ban.

### !avatar
Palavras: avatar, skin, roupa
Perfil → Avatar: pele, cabelo, cores, camisa, calça e acessório (óculos, boné, coroa, fone).

### !studio
Palavras: studio, criar jogo, editor
```
cd Claude-code-data1/Rolox-Studio
pip install -r requirements.txt
python servidor.py
```
Abra http://localhost:8600 → **leve** (celular) ou **PC**. Tem modelos (Obby, Moedas), Ctrl+Z, import .obj e ▶ Jogar. Também pela aba Studio do app.

### !scripts
Palavras: lua, luau, python, script
LocalScript = Lua/Luau, Script (servidor) = Python, ModuleScript = qualquer um. A primeira linha define: `_++linguagemprogroma++_ = lua` ou `= python`.

### !pctocelular
Palavras: pctocelular, controle, bluetooth, cabo
O celular vira controle no Studio PC: inclinar = andar, levantar = pular. Até 5 por Bluetooth e 2 por cabo. Os dados não saem do celular e do PC. Sem sensor = joystick.

### !erros
Palavras: erro, pydantic, not_found, missing, command not found
• **pydantic-core:** `pkg install rust binutils clang make`, depois `export ANDROID_API_LEVEL=$(getprop ro.build.version.sdk)` e instale de novo (ou use o Flask)
• **NOT_FOUND / missing argument:** rode `git pull` em Claude-code-data1
• **flet not found:** `python -m flet run --web --port 8550 src/main.py`
• **Porta em uso:** Ctrl+C na outra sessão do Termux

### !privacidade
Palavras: dados, lgpd, privacidade
A localização só é guardada com permissão. Alertas e tentativas de login somem em 30 dias, e as senhas tentadas ficam criptografadas.

### !links
Palavras: link, discord, github
https://discord.gg/Wb39E7vgh · https://github.com/a30208777-ai/Claude-code-data1
⚠️ A equipe nunca pede sua senha.
