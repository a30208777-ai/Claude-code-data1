"""Busca do ROLOX: jogadores, jogos e itens, em ORDEM DE RELEVÂNCIA.

Nível (menor = melhor):
  0 igual ao termo · 1 começa com o termo · 2 alguma palavra começa com o termo · 3 contém
Dentro do nível: nomes mais curtos primeiro. "exemp" acha exemp, exemp1, exemp2... antes de
"meu.exemp" e "xexempx". Jogadores e jogos são ordenados assim no banco; itens, aqui.
"""

from __future__ import annotations

import re
import unicodedata

import avatar as avatar_mod

NIVEIS = {0: "exato", 1: "começa com", 2: "palavra", 3: "contém"}
MIN, MAX = 2, 40


def normalizar(texto: str) -> str:
    """minúsculas e sem acento: 'Óculos' == 'oculos'."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def termo_valido(termo: str) -> str:
    t = normalizar(termo)
    return t if MIN <= len(t) <= MAX else ""


def nivel(nome: str, termo: str) -> int | None:
    n, t = normalizar(nome), normalizar(termo)
    if not t or t not in n:
        return None
    if n == t:
        return 0
    if n.startswith(t):
        return 1
    if re.search(r"[\s._\-]" + re.escape(t), n):
        return 2
    return 3


def catalogo_itens() -> list[dict]:
    """Itens que existem hoje: os do avatar (vestir é grátis)."""
    itens = []
    for v, nome in avatar_mod.CABELOS.items():
        itens.append({"nome": f"Cabelo {nome}", "tipo": "Cabelo", "campo": "cabelo", "valor": v, "emoji": "💇"})
    for v, nome in avatar_mod.ACESSORIOS.items():
        if v != "nenhum":
            itens.append({"nome": nome, "tipo": "Acessório", "campo": "acessorio", "valor": v, "emoji": "🎩"})
    for nome, cor in avatar_mod.CORES.items():
        itens.append({"nome": f"Camisa {nome}", "tipo": "Camisa", "campo": "camisa", "valor": cor, "emoji": "👕", "cor": cor})
        itens.append({"nome": f"Calça {nome}", "tipo": "Calça", "campo": "calca", "valor": cor, "emoji": "👖", "cor": cor})
        itens.append({"nome": f"Cabelo cor {nome}", "tipo": "Cor do cabelo", "campo": "cor_cabelo", "valor": cor, "emoji": "🎨", "cor": cor})
    for nome, cor in avatar_mod.PELES.items():
        itens.append({"nome": f"Pele {nome}", "tipo": "Pele", "campo": "pele", "valor": cor, "emoji": "🧑", "cor": cor})
    return itens


def buscar_itens(termo: str, limite: int = 20) -> list[dict]:
    t = termo_valido(termo)
    if not t:
        return []
    achados = []
    for item in catalogo_itens():
        # o tipo também conta: "camisa" acha todas as camisas, "oculos" acha Óculos
        nv = min((x for x in (nivel(item["nome"], t), nivel(item["tipo"], t)) if x is not None), default=None)
        if nv is not None:
            achados.append({**item, "nivel": nv})
    achados.sort(key=lambda i: (i["nivel"], len(i["nome"]), normalizar(i["nome"])))
    return achados[:limite]


def item_valido(campo: str, valor: str) -> bool:
    return any(i["campo"] == campo and i["valor"] == valor for i in catalogo_itens())
