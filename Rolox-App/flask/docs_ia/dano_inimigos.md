palavras: dano, morrer, morte, matar, vida, espinho, armadilha, inimigo, inimigos, monstro, zumbi, npc, perseguir, seguir, bomba, explosao, explodir, cura, curar, kit medico, perigo

# Receita: dano, cura e inimigos
- Vida: `h.Health` (0..h.MaxHealth, normal 100). `h:TakeDamage(20)` tira vida. Health = 0 → morre e renasce em 2 s.
- `h.Died:Connect(function() ... end)` avisa quando morreu.

## Espinho que tira 25 de vida (com intervalo)
```lua
local espinho = workspace:FindFirstChild("Espinho")
local pronto = true
espinho.Touched:Connect(function(outro)
  local h = outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")
  if not h or not pronto then return end
  pronto = false
  h:TakeDamage(25)
  game:GetService("Sons"):Tocar("dano")
  wait(0.8)
  pronto = true
end)
```
## Cura
Part verde "Cura": no Touched `h.Health = h.MaxHealth`, som "moeda", some por 10 s (Transparency 1, CanCollide false) e volta.

## Inimigo simples que persegue (bloco que anda até o jogador)
```lua
local inimigo = workspace:FindFirstChild("Inimigo")
local jogador = game.Players.LocalPlayer
local VEL = 8
game:GetService("RunService").Heartbeat:Connect(function(dt)
  local raiz = jogador.Character and jogador.Character:FindFirstChild("HumanoidRootPart")
  if not raiz then return end
  local dir = raiz.Position - inimigo.Position
  dir = Vector3.new(dir.X, 0, dir.Z)
  if dir.Magnitude > 1 then
    inimigo.Position = inimigo.Position + dir.Unit * VEL * dt
  end
end)
-- e um Touched no inimigo igual ao do espinho para dar dano
```
Num jogo multijogador o inimigo deve andar no Script (Python) para todos verem o mesmo; persiga o jogador mais perto
usando `game.Players.GetPlayers()`.

## Explosão
`game:GetService("Sons"):Tocar("explosao")`, dano em quem está perto:
`if (raiz.Position - bomba.Position).Magnitude < 10 then h:TakeDamage(60) end`, depois `bomba:Destroy()`.
