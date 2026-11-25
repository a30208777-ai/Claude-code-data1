# VISTA Hacks

App dos **servidores de hack/mod** do VISTA.

- Quem joga aqui **não encontra os jogadores do VISTA normal**: ao tocar em "🤖 Jogar com hacks", a conta entra no
  modo hack daquele jogo e o banco do VISTA só deixa entrar em servidores hack (e servidor hack só aceita quem está no
  modo hack).
- No jogo, o botão **🤖** lá em cima abre o **executor**: escreva Lua (a mesma API dos LocalScripts) ou escolha um dos
  scripts prontos (velocidade, super pulo, voar, vida infinita, chuva de bolas, explosão, mapa arco-íris...).
- No modo hack **não vale recorde, Cofre nem emblema** (o servidor recusa).
- Para voltar ao normal: na área de hacks, "Sair do modo hack".

O app abre a área `/hacks` do site do VISTA dentro dele (WebView). No PC, abre no navegador.

    flet run src/main.py
    python -m pytest -q
