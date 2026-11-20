palavras: multijogador, multiplayer, todos, todos os jogadores, outros jogadores, servidor, rede, sincronizar, online, time, times, equipe, pvp, chat, mensagem para todos, anfitriao

# Receita: multijogador no ROLOX (modelo anfitrião)
- Script (Python, em ServerScriptService) roda em UM aparelho, o do anfitrião. O que ele muda nas PEÇAS
  (Position, Color, Transparency, CanCollide, criar/apagar) aparece para TODOS automaticamente.
- LocalScript (Lua) roda em cada jogador: tela, sons, controles, Cofre e Emblemas do próprio jogador.
- Mensagens entre eles com o serviço Rede (dados: texto, número ou true/false):
  LocalScript → `game:GetService("Rede"):ParaServidor("nome", dados)`
  Script      → `rede.Recebido.Connect(funcao(jogador, nome, dados))`
  Script      → `rede.ParaTodos("nome", dados)` ou `rede.ParaJogador(jogador, "nome", dados)`
  LocalScript → `rede.RecebidoDoServidor:Connect(function(nome, dados) ... end)`

## Exemplo: botão na tela que acende uma luz para todos
```acoes
[
 {"acao":"criar","classe":"Part","nome":"Luz","pai":"Workspace","posicao":[0,6,0],"tamanho":[2,2,2],"forma":"Ball","cor":"#555555"},
 {"acao":"criar","classe":"LocalScript","nome":"BotaoLuz","pai":"StarterPlayerScripts","linguagem":"lua",
  "codigo":"local tela = game:GetService(\"Tela\")\nlocal rede = game:GetService(\"Rede\")\ntela:Botao(\"luz\", \"💡 Luz\", \"baixo\")\ntela.Clicado:Connect(function(id)\n  if id == \"luz\" then rede:ParaServidor(\"luz\", true) end\nend)\nrede.RecebidoDoServidor:Connect(function(nome, dados)\n  if nome == \"aviso\" then tela:Aviso(dados, 2) end\nend)"},
 {"acao":"criar","classe":"Script","nome":"ServidorLuz","pai":"ServerScriptService","linguagem":"python",
  "codigo":"rede = game.GetService(\"Rede\")\nluz = workspace.Luz\nacesa = False\n\ndef recebeu(jogador, nome, dados):\n    global acesa\n    if nome != \"luz\":\n        return\n    acesa = not acesa\n    luz.Color = Color3.fromRGB(255, 235, 59) if acesa else Color3.fromRGB(85, 85, 85)\n    rede.ParaTodos(\"aviso\", f\"{jogador.Name} {'acendeu' if acesa else 'apagou'} a luz\")\n\nrede.Recebido.Connect(recebeu)"}
]
```
Regra: placar geral, portas, rodadas e qualquer coisa que todos precisam ver igual → Script. Nunca confie num número
que veio do jogador (ex.: "ganhei 1000 moedas"): o Script confere.
