# ROLOX — Bot do Discord e registros de moderação

## O que faz
- **Respostas automáticas** com o arquivo `Fases/ROLOX_DISCORD.md`:
  - com comando: `!fases`, `!tickets`, `!studio`…;
  - com palavras-chave: quando a mensagem é uma pergunta (termina com `?`) ou marca o bot. A mesma resposta não se repete no canal por 90 segundos.
- **Registros nos webhooks:**
  - **Banimentos:** ban, desban, IP bloqueado e IP desbloqueado.
  - **Punições:** sem chat, chat liberado e aviso.

## De onde vêm os registros
- **Discord (este bot):**
  - `!ban @membro motivo` e `!desban ID motivo`;
  - `!semchat @membro 10m motivo` (tempo em `m`, `h` ou `d`, até 28 dias) e `!comchat @membro`;
  - `!aviso @membro motivo`.

  Banimentos e castigos feitos pelo **menu do próprio Discord** também são registrados.
- **Jogo ROLOX (app Flet ou Flask, painel ADM):**
  - banir (pede o motivo) e desbanir;
  - **sem chat** (10 min a 7 dias, com motivo) e devolver o chat;
  - desbloquear IP.

  Os **IPs bloqueados automaticamente** (3 senhas erradas) são registrados quando um ADM abre o painel, uma vez só.

Cada registro mostra quem foi punido, quem puniu, onde (Discord ou Jogo ROLOX), o motivo e, no sem chat, a duração e até quando vale. O registro nunca marca ninguém, nem se o motivo tiver `@everyone`.

## Configurar
1. Copie `rolox.env.exemplo` para **`~/.rolox.env`** e preencha o token do bot e os dois webhooks.
   ⚠️ **Nunca** coloque esse arquivo no GitHub nem cole os links no Discord: quem tem o link de um webhook consegue postar no canal. Se vazar, no Discord vá em Configurações do canal → Integrações → Webhooks e gere um link novo.
2. No [Discord Developer Portal](https://discord.com/developers/applications), abra o seu app e vá em **Bot**:
   - ligue **Message Content Intent** e **Server Members Intent**;
   - convide o bot com as permissões *Ler/Enviar mensagens*, *Banir membros*, *Castigar membros* e *Ver registro de auditoria*.
3. O cargo do bot precisa ficar **acima** dos cargos que ele vai punir.

## Rodar
```bash
cd Claude-code-data1/Rolox-Discord
pip install -r requirements.txt
python bot.py
```
No Termux, se o `aiohttp` (usado pelo discord.py) não compilar, rode com `AIOHTTP_NO_EXTENSIONS=1 pip install -r requirements.txt`.

O app Flet e o Flask leem o **mesmo** `~/.rolox.env`. O painel ADM mostra "Registros no Discord: banimentos ligado/desligado".

## Testes
```bash
pip install pytest && python -m pytest -q    # 14 testes, sem internet
```
O arquivo `discord_log.py` existe em três lugares: aqui, em `Rolox-App/mobile/src/rolox/` e em `Rolox-App/flask/`. Um teste confere se as três cópias continuam iguais.
