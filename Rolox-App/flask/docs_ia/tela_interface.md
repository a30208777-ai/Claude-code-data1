palavras: tela, interface, ui, gui, hud, texto, botao, botoes, barra, vida, menu, aviso, mensagem, mostrar, contador, loja do jogo, painel

# Receita: coisas na tela (Tela)
Só no LocalScript (cada jogador vê a sua tela). `local tela = game:GetService("Tela")`
- tela:Texto(id, texto, lugar)        → cria ou ATUALIZA (mesmo id = troca o texto)
- tela:Botao(id, texto, lugar)        → botão; clique chega em tela.Clicado:Connect(function(id) ... end)
- tela:Barra(id, valor, maximo, lugar)
- tela:Aviso(texto, segundos)         → mensagem grande no meio que some sozinha
- tela:Remover(id) / tela:Limpar()
Lugares: "topo", "centro", "baixo", "esquerda", "direita". id: só letras, números, _ ou -.
O texto é sempre texto puro (HTML não funciona). Máximo 200 letras no Texto e 40 no Botão.

## Barra de vida que acompanha o jogador
```lua
local tela = game:GetService("Tela")
local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
game:GetService("RunService").Heartbeat:Connect(function()
  tela:Barra("vida", h.Health, h.MaxHealth, "topo")
end)
```

## Menu com vários botões (loja dentro do jogo)
```lua
local tela = game:GetService("Tela")
local cofre = game:GetService("Cofre")
local moedas = cofre:Ler("moedas", 0)
local function atualizar() tela:Texto("saldo", "🪙 " .. moedas, "topo") end
atualizar()
tela:Botao("velocidade", "⚡ Velocidade (5🪙)", "direita")
tela:Botao("pulo", "🦘 Super pulo (8🪙)", "direita")
tela.Clicado:Connect(function(id)
  local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
  if id == "velocidade" and moedas >= 5 then
    moedas = moedas - 5; h.WalkSpeed = 28
  elseif id == "pulo" and moedas >= 8 then
    moedas = moedas - 8; h.JumpPower = 80
  else
    tela:Aviso("Moedas insuficientes", 2); return
  end
  cofre:Salvar("moedas", moedas)
  game:GetService("Sons"):Tocar("clique")
  atualizar()
end)
```
