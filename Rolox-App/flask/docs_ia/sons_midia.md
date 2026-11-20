palavras: som, sons, musica, audio, barulho, efeito sonoro, tocar, video, filme, telao, tv, televisao, cinema, trilha

# Receita: sons, música e vídeo
## Sons prontos (gerados na hora, sem arquivo)
`game:GetService("Sons"):Tocar(nome)` com nome = moeda, pulo, vitoria, dano, clique, porta, explosao, erro.
Música de fundo: `game:GetService("Sons"):Musica("calma")` ou "acao"; `Sons:Musica("")` para parar.

## Som ou vídeo do próprio criador
O usuário envia o arquivo pelo botão 🎵 Som/Vídeo do Studio (você NÃO consegue enviar arquivo). Depois disso aparece
no mapa um objeto **Som** (propriedades Volume 0..1, Repetir, TocarAoComecar) ou uma peça **TelaVideo** (ComSom, Repetir).
Nos scripts: `workspace.Musica:Tocar()` e `workspace.Musica:Parar()`; `workspace.Telao:Tocar()`.
Se o usuário pedir uma música específica, explique que ele precisa enviar o arquivo dele pelo botão 🎵 e diga o nome
que você vai usar no script (ex.: "Musica"); você pode já deixar o script pronto usando FindFirstChild para não dar erro:
```lua
local m = workspace:FindFirstChild("Musica")
if m then m:Tocar() else game:GetService("Sons"):Musica("calma") end
```
## Som ao tocar numa peça
```lua
local sino = workspace:FindFirstChild("Sino")
local pronto = true
sino.Touched:Connect(function(outro)
  if not pronto or not (outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")) then return end
  pronto = false
  game:GetService("Sons"):Tocar("vitoria")
  wait(1)
  pronto = true
end)
```
