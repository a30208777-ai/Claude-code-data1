palavras: material, materiais, madeira, metal, grama, pedra, tijolo, concreto, areia, gelo, neon, vidro, tecido, borracha, lava, agua, textura, brilhar, brilhante, transparente, escorregar, escorregadio, quicar, trampolim, ceu, noite, dia, por do sol, amanhecer, neblina, nevoa, estrelas, hora, iluminacao, clima, ambiente

# Materiais das peças e o Céu
## Materiais (propriedade Material; no bloco acoes use "material": "Madeira")
Plastico (padrão), Madeira, Metal, Grama, Pedra, Tijolo, Concreto, Areia, Gelo, Neon, Vidro, Tecido, Borracha, Lava, Agua, Pinos (visual clássico de blocos).
A COR continua valendo: Madeira + "#8d6e63" = madeira marrom; Madeira + "#fafafa" = madeira clara.
Materiais que mudam o jogo de verdade:
- Gelo: o jogador escorrega (demora para acelerar e para parar).
- Areia: o jogador anda mais devagar.
- Borracha: o pulo é bem mais alto em cima dela e quem cai nela quica (bom para trampolim).
- Neon e Lava brilham sozinhos (ótimo à noite). Vidro e Agua são transparentes. Agua se mexe.
Lava NÃO tira vida sozinha: se quiser que machuque, coloque o script de dano (veja dano/obby).

```acoes
[
 {"acao":"criar","classe":"Part","nome":"PistaGelo","pai":"Workspace","posicao":[0,0.5,-20],"tamanho":[12,1,30],"cor":"#b3e5fc","material":"Gelo"},
 {"acao":"criar","classe":"Part","nome":"Trampolim","pai":"Workspace","posicao":[10,0.5,0],"tamanho":[6,1,6],"cor":"#e91e63","material":"Borracha"},
 {"acao":"criar","classe":"Part","nome":"Placa","pai":"Workspace","posicao":[-8,4,0],"tamanho":[6,2,0.5],"cor":"#00e5ff","material":"Neon"},
 {"acao":"ceu","hora":19,"neblina":0.2}
]
```
No script: `workspace.Piso.Material = "Gelo"` (Lua) / `workspace.Piso.Material = "Gelo"` (Python). Nome errado dá erro.

## Céu (hora do dia, neblina, estrelas)
Ação {"acao":"ceu","hora":0..24,"neblina":0..1,"estrelas":true} muda o céu do mapa (fica salvo).
Nos scripts (LocalScript: cada um vê o seu): `local ceu = game:GetService("Ceu")`; `ceu.Hora = 18`; `ceu.Neblina = 0.5`; `ceu.Estrelas = true`.
6 = amanhecer, 12 = meio-dia, 18 = pôr do sol, 21 a 4 = noite com estrelas.
Ciclo de dia e noite (1 dia = 4 minutos):
```lua
local ceu = game:GetService("Ceu")
game:GetService("RunService").Heartbeat:Connect(function(dt)
  ceu.Hora = ceu.Hora + dt * (24 / 240)
end)
```
