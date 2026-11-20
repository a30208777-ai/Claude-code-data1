palavras: animar, animacao, animado, suave, deslizar, mover, girar, crescer, encolher, sumir, aparecer, piscar, elevador, plataforma, vai e volta, efeito, efeitos, explosao, explodir, bomba, confete, festa, fumaca, brilho, laser, tiro, arma, mirar, raio, raycast, enxergar, linha de visao, detectar parede

# Animar, Efeitos e Raio
## Animar: mexe peças suavemente sem escrever laço
`local anim = game:GetService("Animar")`
- `anim:Mover(peca, Vector3.new(x, y, z), segundos, estilo)` → vai até a posição
- `anim:Girar(peca, Vector3.new(0, 180, 0), s)` · `anim:Tamanho(peca, Vector3.new(8, 1, 8), s)` · `anim:Cor(peca, Color3.fromRGB(255,0,0), s)`
- `anim:Sumir(peca, s)` (fica invisível e sem colisão) · `anim:Aparecer(peca, s)`
- `anim:VaiEVolta(peca, Vector3.new(0, 8, 0), s)` → vai e volta para sempre (elevador, plataforma móvel)
- `anim:Parar(peca)` · `anim.Terminou:Connect(function(peca, tipo) ... end)`
Estilos: "linear", "suave" (padrão), "quicar", "elastico". Animações feitas no Script (Python) aparecem para todos.

```acoes
[
 {"acao":"criar","classe":"Part","nome":"Elevador","pai":"Workspace","posicao":[0,0.5,-12],"tamanho":[6,1,6],"cor":"#90a4ae","material":"Metal"},
 {"acao":"criar","classe":"Part","nome":"Botao","pai":"Workspace","posicao":[6,0.5,-6],"tamanho":[2,1,2],"cor":"#f44336","material":"Neon"},
 {"acao":"criar","classe":"LocalScript","nome":"Animacoes","pai":"StarterPlayerScripts","linguagem":"lua",
  "codigo":"local anim = game:GetService(\"Animar\")\nlocal fx = game:GetService(\"Efeitos\")\nanim:VaiEVolta(workspace.Elevador, Vector3.new(0, 15, 0), 4)\n\nlocal pronto = true\nworkspace.Botao.Touched:Connect(function(outro)\n  if not pronto or not (outro.Parent and outro.Parent:FindFirstChildOfClass(\"Humanoid\")) then return end\n  pronto = false\n  fx:Confete(workspace.Botao.Position + Vector3.new(0, 3, 0))\n  anim:Cor(workspace.Botao, Color3.fromRGB(76, 175, 80), 0.5)\n  wait(2)\n  anim:Cor(workspace.Botao, Color3.fromRGB(244, 67, 54), 0.5)\n  pronto = true\nend)"}
]
```

## Efeitos
`local fx = game:GetService("Efeitos")`
- `fx:Explosao(posicao, raio)` → clarão, som, empurra peças soltas e dá dano em quem está perto (até 100 no centro). Devolve quantos jogadores atingiu.
  `fx:Explosao(pos, raio, false)` = só o visual, sem dano.
- `fx:Confete(posicao)` (vitória!) · `fx:Fumaca(posicao)` · `fx:Brilho(peca, segundos)` (pisca brilhando)
Efeitos aparecem para quem rodou o script: para todos verem, mande pela Rede e cada LocalScript mostra.

## Raio: o que tem na frente?
`local r = workspace:Raio(origem, direcao, distancia, ignorar)` → nil ou uma tabela { Peca, Posicao, Distancia }.
`ignorar` = uma peça ou Model para não contar (ex.: o próprio personagem).
```lua
local jogador = game.Players.LocalPlayer
local tela = game:GetService("Tela")
tela:Botao("tiro", "🔫 Atirar", "direita")
tela.Clicado:Connect(function(id)
  if id ~= "tiro" then return end
  local raiz = jogador.Character.HumanoidRootPart
  local frente = jogador.Character:FindFirstChildOfClass("Humanoid").MoveDirection
  if frente.Magnitude < 0.1 then frente = Vector3.new(0, 0, -1) end
  local r = workspace:Raio(raiz.Position, frente, 80, jogador.Character)
  if r then
    game:GetService("Efeitos"):Explosao(r.Posicao, 4, false)
    if r.Peca.Name == "Alvo" then tela:Aviso("🎯 Acertou!", 2) end
  end
end)
```
Em Python o resultado tem os mesmos campos: `r = workspace.Raio(origem, direcao, 50)`; `if r: print(r.Peca.Name, r.Distancia)`.
