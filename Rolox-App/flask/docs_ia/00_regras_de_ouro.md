palavras: -
sempre: sim

# Regras de ouro (sempre siga)
1. Faça TUDO num bloco ```acoes: crie as peças que o script usa ANTES do script, no mesmo bloco.
2. Nomes sem espaço e sem acento (Porta, Moeda1, BotaoAbrir). O script acha a peça por esse nome: workspace:FindFirstChild("Porta").
3. Lua (LocalScript em StarterPlayerScripts) usa `:` para métodos (peca.Touched:Connect, tela:Texto) e `end`.
   Python (Script em ServerScriptService) usa `.` (peca.Touched.Connect) e `async def` + `await wait(s)`.
4. Touched: SEMPRE confira se é jogador: `local h = outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")`.
5. Use um "debounce" (variavel `pronto`) para o toque não disparar 30 vezes por segundo.
6. Posição: o chão é y=0. Peça de altura h apoiada no chão: y = h/2. Peça em cima de outra: some as alturas.
7. Em loops infinitos SEMPRE tenha `wait(...)` dentro (sem isso o jogo trava).
8. Cor é "#rrggbb". Peças novas já vêm ancoradas (não caem); use "ancorada": false só para coisa que deve cair.
9. Se o pedido é grande (um jogo inteiro), faça um jogo pequeno que FUNCIONA, e diga o que dá para adicionar depois.
10. Nunca invente serviço: só existem Players, RunService, Rede, Cofre, Tela, Sons, Emblemas, Internet, Animar, Efeitos, Ceu.
11. Capriche no visual: escolha "material" (Madeira, Grama, Pedra, Tijolo, Metal, Neon...) e cores que combinem.
