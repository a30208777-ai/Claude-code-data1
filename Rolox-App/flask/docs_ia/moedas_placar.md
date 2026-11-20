palavras: moeda, moedas, coletar, coletavel, pegar, item, gema, diamante, ponto, pontos, placar, leaderstats, ranking, recorde, score, dinheiro, coins

# Receita: moedas que dá para pegar + placar
- As moedas ficam numa pasta (Folder) "Moedas" no Workspace; o script percorre a pasta.
- Placar do site = pasta "leaderstats" dentro do jogador com um IntValue (o 1º valor vira recorde no site).
- Para o progresso ficar salvo entre partidas use o Cofre.

```acoes
[
 {"acao":"criar","classe":"Folder","nome":"Moedas","pai":"Workspace"},
 {"acao":"criar","classe":"Part","nome":"Moeda1","pai":"Workspace.Moedas","posicao":[5,2,0],"tamanho":[2,2,2],"forma":"Cylinder","cor":"#ffc400","colide":false},
 {"acao":"criar","classe":"Part","nome":"Moeda2","pai":"Workspace.Moedas","posicao":[10,2,5],"tamanho":[2,2,2],"forma":"Cylinder","cor":"#ffc400","colide":false},
 {"acao":"criar","classe":"Part","nome":"Moeda3","pai":"Workspace.Moedas","posicao":[-6,2,8],"tamanho":[2,2,2],"forma":"Cylinder","cor":"#ffc400","colide":false},
 {"acao":"criar","classe":"LocalScript","nome":"PegarMoedas","pai":"StarterPlayerScripts","linguagem":"lua",
  "codigo":"local jogador = game.Players.LocalPlayer\nlocal tela = game:GetService(\"Tela\")\nlocal sons = game:GetService(\"Sons\")\nlocal cofre = game:GetService(\"Cofre\")\n\nlocal stats = Instance.new(\"Folder\", jogador)\nstats.Name = \"leaderstats\"\nlocal moedas = Instance.new(\"IntValue\", stats)\nmoedas.Name = \"Moedas\"\nmoedas.Value = 0\n\nlocal total = cofre:Ler(\"total_moedas\", 0)\ntela:Texto(\"moedas\", \"🪙 0  (total: \" .. total .. \")\", \"topo\")\n\nfor _, m in ipairs(workspace.Moedas:GetChildren()) do\n  local pega = false\n  m.Touched:Connect(function(outro)\n    if pega then return end\n    if not (outro.Parent and outro.Parent:FindFirstChildOfClass(\"Humanoid\")) then return end\n    pega = true\n    m:Destroy()\n    sons:Tocar(\"moeda\")\n    moedas.Value = moedas.Value + 1\n    total = cofre:Somar(\"total_moedas\", 1)\n    tela:Texto(\"moedas\", \"🪙 \" .. moedas.Value .. \"  (total: \" .. total .. \")\", \"topo\")\n  end)\nend\n\n-- moeda girando\ngame:GetService(\"RunService\").Heartbeat:Connect(function(dt)\n  for _, m in ipairs(workspace.Moedas:GetChildren()) do\n    m.Rotation = m.Rotation + Vector3.new(0, 120 * dt, 0)\n  end\nend)"}
]
```
Para muitas moedas: crie várias ações "criar" com nomes Moeda1, Moeda2... em posições diferentes (pode fazer uma fileira somando 5 no x).
Venceu quando pegou todas: `if #workspace.Moedas:GetChildren() == 0 then tela:Aviso("Pegou todas! 🎉", 4) end`.
