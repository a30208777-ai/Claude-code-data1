"""Curiosidades do VISTA mostradas na tela "Carregando" (app e site).

Para adicionar uma: escreva mais uma linha na lista. A MESMA lista existe no site
(Rolox-App/flask/curiosidades.py) — um teste confere que as duas são iguais.
"""

from __future__ import annotations

import random

CURIOSIDADES = [
    "O VISTA foi inspirado no ROBLOX.",
    "O VISTA foi criado por causa das decisões ruins do ROBLOX atualmente.",
    "No VISTA Studio você programa em Lua ou em Python — você escolhe.",
    "Todo mapa enviado é testado e aprovado pelo dono antes de aparecer em Jogos.",
    "A IA do Studio monta o jogo sozinha: cria as peças, as portas e os scripts.",
    "Cada mensagem para a IA do Studio custa 10 tickets.",
    "Todo dia tem presente de tickets — e no dia seguinte você ganha mais.",
    "Existem 15 materiais no Studio. No Gelo você escorrega e na Borracha você pula bem mais alto!",
    "Os sons do VISTA não são arquivos: eles são criados na hora pelo próprio jogo.",
    "A logo do VISTA foi desenhada por código, sem nenhum programa de desenho.",
    "No multijogador, um dos jogadores é o anfitrião: os Scripts rodam no aparelho dele.",
    "Se o anfitrião sair, outro jogador assume e o jogo continua de onde parou.",
    "Os jogos podem pesquisar na internet, sempre com busca segura.",
    "Parceiros do VISTA ganham um selo 🤝 ao lado do nome e podem mostrar suas redes sociais.",
    "O Céu do Studio tem hora do dia: às 18h tem pôr do sol e de noite aparecem estrelas.",
    "Os criadores podem colocar seus próprios sons e vídeos nos jogos.",
    "3 senhas erradas bloqueiam o aparelho que errou, e o dono da conta é avisado.",
    "Na Loja você troca tickets por cores especiais para o avatar, como Dourado e Galáxia.",
    "Emblemas ganhos nos jogos ficam para sempre no seu perfil.",
    "O app do VISTA para PC chega no fim deste ano para os ADMs e em 2029 para todo mundo.",
    "Dá para usar o celular como controle do jogo no PC, inclinando o aparelho.",
    "O VISTA funciona no celular e no navegador, com a mesma conta.",
]


def embaralhadas(semente=None) -> list[str]:
    """Todas as curiosidades em ordem aleatória (sem repetir até acabar)."""
    lista = list(CURIOSIDADES)
    random.Random(semente).shuffle(lista)
    return lista
