"""Avatar do Rolox — primeiro passo: boneco em blocos com cores e estilos.

O avatar fica salvo em perfis.avatar (jsonb) como:
    {"pele": "#c68642", "cabelo": "curto", "cor_cabelo": "#3b2219",
     "camisa": "#1e88e5", "calca": "#37474f", "acessorio": "nenhum"}

`pecas(avatar)` devolve a lista de retângulos (x, y, largura, altura, cor, raio)
num quadro de 120 x 200; o Flet e o Flask desenham a partir dela.
"""

from __future__ import annotations

LARGURA, ALTURA = 120, 200

PELES = {
    "Clara": "#f5d0b5", "Média clara": "#e0ac69", "Média": "#c68642",
    "Morena": "#8d5524", "Escura": "#5c3a1e", "Azul (fantasia)": "#64b5f6",
}
CORES = {
    "Preto": "#212121", "Castanho": "#3b2219", "Loiro": "#e6c35c", "Ruivo": "#b5462b",
    "Branco": "#eeeeee", "Azul": "#1e88e5", "Vermelho": "#e53935", "Verde": "#43a047",
    "Roxo": "#7e57c2", "Rosa": "#ec407a", "Laranja": "#fb8c00", "Cinza": "#607d8b",
    "Amarelo": "#fdd835", "Jeans": "#37474f",
}
CABELOS = {"curto": "Curto", "longo": "Longo", "moicano": "Moicano", "topete": "Topete", "careca": "Careca"}
ACESSORIOS = {"nenhum": "Nenhum", "oculos": "Óculos", "bone": "Boné", "coroa": "Coroa", "fone": "Fone"}

PADRAO = {
    "pele": "#c68642", "cabelo": "curto", "cor_cabelo": "#3b2219",
    "camisa": "#1e88e5", "calca": "#37474f", "acessorio": "nenhum",
}

_CORES_VALIDAS = set(PELES.values()) | set(CORES.values())


def normalizar(avatar: dict | None) -> dict:
    """Completa com o padrão e descarta valores fora das opções."""
    a = dict(PADRAO)
    for k, v in (avatar or {}).items():
        if k not in PADRAO or not isinstance(v, str):
            continue
        if k == "cabelo" and v in CABELOS:
            a[k] = v
        elif k == "acessorio" and v in ACESSORIOS:
            a[k] = v
        elif k in ("pele", "cor_cabelo", "camisa", "calca") and v in _CORES_VALIDAS:
            a[k] = v
    return a


def pecas(avatar: dict | None) -> list[tuple[int, int, int, int, str, int]]:
    """Retângulos do boneco, de trás para a frente: (x, y, l, a, cor, raio)."""
    a = normalizar(avatar)
    pele, cab, camisa, calca = a["pele"], a["cor_cabelo"], a["camisa"], a["calca"]
    p: list[tuple[int, int, int, int, str, int]] = []

    if a["cabelo"] == "longo":                      # cabelo atrás da cabeça
        p.append((34, 16, 52, 62, cab, 10))

    p += [
        (35, 130, 22, 64, calca, 4), (63, 130, 22, 64, calca, 4),   # pernas
        (33, 188, 26, 8, "#263238", 3), (61, 188, 26, 8, "#263238", 3),  # sapatos
        (12, 72, 18, 46, camisa, 6), (90, 72, 18, 46, camisa, 6),     # braços
        (13, 116, 16, 12, pele, 5), (91, 116, 16, 12, pele, 5),       # mãos
        (30, 70, 60, 64, camisa, 8),                                  # tronco
        (52, 62, 16, 10, pele, 2),                                    # pescoço
        (38, 20, 44, 44, pele, 10),                                   # cabeça
        (48, 36, 6, 7, "#212121", 2), (66, 36, 6, 7, "#212121", 2),   # olhos
        (52, 52, 16, 3, "#6d4c41", 2),                                # boca
    ]

    estilo = a["cabelo"]
    if estilo in ("curto", "longo"):
        p.append((36, 14, 48, 14, cab, 8))
    elif estilo == "moicano":
        p.append((53, 4, 14, 22, cab, 4))
    elif estilo == "topete":
        p += [(36, 16, 48, 10, cab, 6), (40, 6, 30, 14, cab, 8)]

    ac = a["acessorio"]
    if ac == "oculos":
        p += [(44, 33, 14, 12, "#263238", 3), (62, 33, 14, 12, "#263238", 3), (58, 37, 4, 3, "#263238", 1)]
    elif ac == "bone":
        p += [(34, 10, 52, 16, "#e53935", 8), (60, 22, 34, 6, "#c62828", 3)]
    elif ac == "coroa":
        p += [(40, 4, 40, 12, "#fbc02d", 2), (40, 0, 8, 8, "#fbc02d", 1),
              (56, 0, 8, 8, "#fbc02d", 1), (72, 0, 8, 8, "#fbc02d", 1)]
    elif ac == "fone":
        p += [(32, 12, 56, 6, "#424242", 3), (30, 30, 10, 18, "#424242", 4), (80, 30, 10, 18, "#424242", 4)]
    return p
