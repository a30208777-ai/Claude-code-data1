palavras: tempo, timer, cronometro, contagem, regressiva, rodada, rodadas, partida, segundos, minuto, relogio, esperar, repetir, loop, intervalo, corrida, quem chega primeiro

# Receita: tempo, cronômetro e rodadas
## Cronômetro de corrida (do início até a chegada)
```lua
local tela = game:GetService("Tela")
local t, correndo = 0, true
game:GetService("RunService").Heartbeat:Connect(function(dt)
  if not correndo then return end
  t = t + dt
  tela:Texto("tempo", string.format("⏱️ %.1f s", t), "topo")
end)
workspace.Chegada.Touched:Connect(function(outro)
  if correndo and outro.Parent == game.Players.LocalPlayer.Character then
    correndo = false
    tela:Aviso(string.format("Chegou em %.1f s!", t), 4)
    local cofre = game:GetService("Cofre")
    if t < cofre:Ler("melhor", 9999) then cofre:Salvar("melhor", t); tela:Aviso("🏅 Novo recorde!", 3) end
  end
end)
```
## Contagem regressiva
```lua
for s = 10, 1, -1 do
  tela:Texto("conta", "⏳ " .. s, "centro")
  wait(1)
end
tela:Remover("conta")
```
## Repetir algo a cada X segundos (sem travar o resto)
```lua
task.spawn(function()
  while true do
    -- faz algo
    wait(5)
  end
end)
```
`task.delay(3, function() ... end)` roda uma vez daqui a 3 s. Rodadas para todos ao mesmo tempo: ver Python (Script) + Rede.ParaTodos.
