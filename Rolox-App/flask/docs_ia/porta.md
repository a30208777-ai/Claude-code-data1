palavras: porta, portao, abrir, fechar, entrada, passagem, parede que some, botao, alavanca, chave, tranca, trancada, senha

# Receita: porta que abre
Porta = uma Part fina. "Abrir" = deixar transparente e sem colisão; "fechar" = voltar ao normal.
Se todos devem ver a porta abrir no multijogador, faça no Script (Python); o exemplo abaixo usa LocalScript (mais simples).

## Porta que abre ao tocar e fecha sozinha depois de 3 s
```acoes
[
 {"acao":"criar","classe":"Part","nome":"Porta","pai":"Workspace","posicao":[0,5,-10],"tamanho":[6,10,1],"cor":"#8d6e63"},
 {"acao":"criar","classe":"LocalScript","nome":"AbrirPorta","pai":"StarterPlayerScripts","linguagem":"lua",
  "codigo":"local porta = workspace:FindFirstChild(\"Porta\")\nlocal aberta = false\n\nporta.Touched:Connect(function(outro)\n  local h = outro.Parent and outro.Parent:FindFirstChildOfClass(\"Humanoid\")\n  if not h or aberta then return end\n  aberta = true\n  porta.Transparency = 0.8\n  porta.CanCollide = false\n  game:GetService(\"Sons\"):Tocar(\"porta\")\n  wait(3)\n  porta.Transparency = 0\n  porta.CanCollide = true\n  aberta = false\nend)"}
]
```
Atenção: com CanCollide = false o Touched continua funcionando (o jogador atravessa).

## Porta com botão na tela
```lua
local tela = game:GetService("Tela")
local porta = workspace:FindFirstChild("Porta")
tela:Botao("abrir", "🚪 Abrir porta", "baixo")
tela.Clicado:Connect(function(id)
  if id ~= "abrir" then return end
  porta.CanCollide = not porta.CanCollide
  porta.Transparency = porta.CanCollide and 0 or 0.8
  tela:Botao("abrir", porta.CanCollide and "🚪 Abrir porta" or "🚪 Fechar porta", "baixo")
end)
```

## Porta com chave (pegar a chave primeiro)
Crie uma Part "Chave" pequena e amarela (tamanho [1,1,2], cor "#ffc400"). No LocalScript: variável `temChave = false`;
Chave.Touched → `temChave = true; chave:Destroy(); tela:Aviso("Você pegou a chave!", 2)`.
Porta.Touched → se `temChave` abre, senão `tela:Aviso("A porta está trancada 🔒", 2)`.

## Porta deslizante (anda para o lado)
```lua
local porta = workspace:FindFirstChild("Porta")
local inicio = porta.Position
for i = 1, 30 do
  porta.Position = inicio + Vector3.new(0, i * 0.33, 0)   -- sobe 10 studs
  wait(0.03)
end
```
