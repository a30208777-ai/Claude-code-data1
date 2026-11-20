palavras: mover, movimento, girar, rodar, rotacao, animacao, animar, subir, descer, elevador, voar, flutuar, teleporte, teletransporte, teleportar, velocidade, correr, pulo alto, super pulo, empurrar, cair, gravidade

# Receita: mover coisas e o jogador
Movimento contínuo = RunService.Heartbeat (roda todo quadro, recebe dt em segundos). Multiplique por dt para ser igual em todo aparelho.

## Girar uma peça
```lua
local p = workspace:FindFirstChild("Roda")
game:GetService("RunService").Heartbeat:Connect(function(dt)
  p.Rotation = p.Rotation + Vector3.new(0, 90 * dt, 0)   -- 90 graus por segundo
end)
```
## Elevador (sobe e desce)
```lua
local e = workspace:FindFirstChild("Elevador")
local base, t = e.Position, 0
game:GetService("RunService").Heartbeat:Connect(function(dt)
  t = t + dt
  e.Position = base + Vector3.new(0, (math.sin(t * 0.8) + 1) * 8, 0)
end)
```
## Teleporte (tocar numa peça e aparecer em outra)
```lua
local de, para = workspace:FindFirstChild("TeleA"), workspace:FindFirstChild("TeleB")
local jogador = game.Players.LocalPlayer
local pronto = true
de.Touched:Connect(function(outro)
  if not pronto or outro.Parent ~= jogador.Character then return end
  pronto = false
  jogador.Character.HumanoidRootPart.Position = para.Position + Vector3.new(0, 4, 0)
  wait(1); pronto = true
end)
```
## Velocidade / super pulo
`local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")`
`h.WalkSpeed = 30` (normal 16) · `h.JumpPower = 90` (normal 50) · gravidade do mundo: `workspace.Gravity = 60` (normal 196.2).
Trampolim: no Touched da peça, `h.Jump = true` com JumpPower alto, e volte ao normal depois de `wait(0.5)`.
Peça que cai: crie com "ancorada": false (cai com a física), ou no script `p.Anchored = false`.
