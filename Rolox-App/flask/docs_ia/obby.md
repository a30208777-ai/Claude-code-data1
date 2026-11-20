palavras: obby, parkour, percurso, obstaculo, obstaculos, lava, plataforma, plataformas, pular, checkpoint, salvar ponto, fase, fases, chegada, final, vitoria, pulo, escada, torre

# Receita: obby (percurso de pulos)
Plano: plataformas de 4x1x4 com espaço de 6 a 8 studs entre elas (o pulo alcança ~8 de distância e ~4 de altura).
Lava = Part vermelha/laranja que zera a vida. Chegada = Part verde que dá vitória.

```acoes
[
 {"acao":"criar","classe":"Folder","nome":"Obby","pai":"Workspace"},
 {"acao":"criar","classe":"Part","nome":"P1","pai":"Workspace.Obby","posicao":[0,2,-12],"tamanho":[4,1,4],"cor":"#42a5f5"},
 {"acao":"criar","classe":"Part","nome":"P2","pai":"Workspace.Obby","posicao":[0,3,-19],"tamanho":[4,1,4],"cor":"#42a5f5"},
 {"acao":"criar","classe":"Part","nome":"P3","pai":"Workspace.Obby","posicao":[5,4,-25],"tamanho":[4,1,4],"cor":"#42a5f5"},
 {"acao":"criar","classe":"Part","nome":"Lava","pai":"Workspace.Obby","posicao":[2,0.6,-20],"tamanho":[30,0.2,24],"cor":"#ff5722"},
 {"acao":"criar","classe":"Part","nome":"Chegada","pai":"Workspace.Obby","posicao":[5,5,-32],"tamanho":[6,1,6],"cor":"#00e676"},
 {"acao":"criar","classe":"LocalScript","nome":"RegrasObby","pai":"StarterPlayerScripts","linguagem":"lua",
  "codigo":"local tela = game:GetService(\"Tela\")\nlocal obby = workspace:FindFirstChild(\"Obby\")\nlocal venceu = false\n\nobby.Lava.Touched:Connect(function(outro)\n  local h = outro.Parent and outro.Parent:FindFirstChildOfClass(\"Humanoid\")\n  if h and h.Health > 0 then\n    h.Health = 0\n    game:GetService(\"Sons\"):Tocar(\"dano\")\n  end\nend)\n\nobby.Chegada.Touched:Connect(function(outro)\n  if venceu then return end\n  if not (outro.Parent and outro.Parent:FindFirstChildOfClass(\"Humanoid\")) then return end\n  venceu = true\n  tela:Aviso(\"🏁 Você completou o obby!\", 4)\n  game:GetService(\"Sons\"):Tocar(\"vitoria\")\n  game:GetService(\"Emblemas\"):Dar(\"zerou\", \"Zerou o Obby\", \"🏆\")\nend)"}
]
```
Quem morre renasce no SpawnLocation depois de 2 s.

## Checkpoint (renascer no último ponto)
```lua
local jogador = game.Players.LocalPlayer
local ultimo = nil
workspace.Obby.Check1.Touched:Connect(function(outro)
  if outro.Parent == jogador.Character and ultimo ~= workspace.Obby.Check1 then
    ultimo = workspace.Obby.Check1
    game:GetService("Tela"):Aviso("✅ Checkpoint!", 2)
  end
end)
local h = jogador.Character:FindFirstChildOfClass("Humanoid")
h.Died:Connect(function()
  wait(2.2)                                   -- espera o renascer automático
  if ultimo then
    jogador.Character.HumanoidRootPart.Position = ultimo.Position + Vector3.new(0, 4, 0)
  end
end)
```

## Plataforma que se move (vai e volta)
```lua
local p = workspace.Obby.P2
local base = p.Position
local t = 0
game:GetService("RunService").Heartbeat:Connect(function(dt)
  t = t + dt
  p.Position = base + Vector3.new(math.sin(t) * 6, 0, 0)
end)
```
Plataforma que some: no Touched, `wait(0.5); p.Transparency = 0.7; p.CanCollide = false; wait(2); p.Transparency = 0; p.CanCollide = true`.
