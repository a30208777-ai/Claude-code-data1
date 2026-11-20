palavras: construir, construcao, casa, predio, castelo, parede, paredes, chao, piso, teto, telhado, escada, ponte, arvore, cidade, mapa, cenario, mundo, cerca, muro, arena, montanha, rua, carro, decoracao, criar mapa, prédio

# Receita: construir com peças (matemática simples)
- Coordenadas: x = esquerda/direita, y = altura, z = frente/trás. O chão do mapa é y = 0.
- Position é o CENTRO da peça. Peça de tamanho [l, a, p] apoiada no chão: y = a/2.
- Duas peças encostadas lado a lado em x: x2 = x1 + (l1 + l2) / 2.
- Agrupe uma construção num Model (ex.: "Casa") e crie as peças com "pai": "Workspace.Casa".

## Casa 12x8x12 (paredes com espessura 1, porta na frente)
```acoes
[
 {"acao":"criar","classe":"Model","nome":"Casa","pai":"Workspace"},
 {"acao":"criar","classe":"Part","nome":"Piso","pai":"Workspace.Casa","posicao":[0,0.5,0],"tamanho":[12,1,12],"cor":"#a1887f"},
 {"acao":"criar","classe":"Part","nome":"ParedeFundo","pai":"Workspace.Casa","posicao":[0,5,-5.5],"tamanho":[12,8,1],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"ParedeEsq","pai":"Workspace.Casa","posicao":[-5.5,5,0],"tamanho":[1,8,12],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"ParedeDir","pai":"Workspace.Casa","posicao":[5.5,5,0],"tamanho":[1,8,12],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"FrenteEsq","pai":"Workspace.Casa","posicao":[-3.75,5,5.5],"tamanho":[4.5,8,1],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"FrenteDir","pai":"Workspace.Casa","posicao":[3.75,5,5.5],"tamanho":[4.5,8,1],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"SobrePorta","pai":"Workspace.Casa","posicao":[0,7.5,5.5],"tamanho":[3,3,1],"cor":"#eeeeee"},
 {"acao":"criar","classe":"Part","nome":"Teto","pai":"Workspace.Casa","posicao":[0,9.5,0],"tamanho":[13,1,13],"cor":"#c62828"}
]
```
(o vão da porta tem 3 de largura e 6 de altura, dá para o jogador passar)

## Escada (degraus de 1 de altura, 2 de profundidade)
Degrau i (começando em 1): posicao [0, i - 0.5, -2*i], tamanho [4, 1, 2]... ou degraus "maciços": tamanho [4, i, 2], y = i/2.
Faça até 15 degraus; acima disso use plataformas.

## Árvore
Tronco: Cylinder tamanho [1.5, 6, 1.5], y = 3, cor "#6d4c41". Copa: Ball tamanho [6, 6, 6], y = 7.5, cor "#2e7d32".

Dicas: muitas peças iguais → use nomes numerados (Arvore1, Arvore2...). Máximo 60 ações por resposta: para um mapa
grande, faça uma parte e diga ao usuário para pedir "continuar".
