"""Documentos que vão junto para a IA do Studio (pasta docs_ia/).

Cada .md tem na 1ª linha `palavras: a, b, c` (e opcionalmente `sempre: sim`). Quando o usuário pede algo,
escolhemos os documentos cujas palavras aparecem no pedido (sem acento, por começo de palavra:
"moedas" acha "moeda") e mandamos o texto deles junto com a instrução. Assim a IA vê receitas
completas e testadas do VISTA em vez de inventar.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PASTA = Path(__file__).with_name("docs_ia")
MAX_DOCS = 3
MAX_CARACTERES = 9000


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


@dataclass
class Doc:
    nome: str
    texto: str
    palavras: list = field(default_factory=list)
    sempre: bool = False


def _raiz(p: str) -> str:
    """'moedas' e 'moeda' se encontram: compara pelo começo (5 letras, ou a palavra toda se for curta)."""
    return p[:5] if len(p) > 5 else p


def carregar(pasta: Path = PASTA) -> list[Doc]:
    docs = []
    for arq in sorted(pasta.glob("*.md")):
        if arq.name.lower() == "readme.md":
            continue
        linhas = arq.read_text(encoding="utf-8").splitlines()
        palavras, sempre, corpo = [], False, 0
        for i, l in enumerate(linhas[:4]):
            if l.lower().startswith("palavras:"):
                palavras = [normalizar(x) for x in l.split(":", 1)[1].split(",") if normalizar(x) not in ("",)]
                corpo = i + 1
            elif l.lower().startswith("sempre:"):
                sempre = normalizar(l.split(":", 1)[1]) in ("sim", "s", "true", "1")
                corpo = i + 1
        texto = "\n".join(linhas[corpo:]).strip()
        if texto:
            docs.append(Doc(arq.stem, texto, palavras, sempre))
    return docs


_DOCS: list[Doc] = carregar() if PASTA.is_dir() else []


def pontuar(doc: Doc, texto_norm: str) -> int:
    tokens = texto_norm.split()
    if not tokens:
        return 0
    junto = f" {texto_norm} "
    pontos = 0
    for p in doc.palavras:
        if " " in p:
            if f" {p} " in junto:
                pontos += 3
        elif p in tokens:
            pontos += 2
        elif len(p) >= 4 and any(t.startswith(_raiz(p)) and len(t) >= 4 for t in tokens):
            pontos += 1
    return pontos


def escolher(mensagens: list[dict], docs: list[Doc] | None = None) -> list[Doc]:
    """Documentos para este pedido: os 'sempre' + até MAX_DOCS que mais combinam.
    O último pedido vale mais; os 2 anteriores ajudam quando o usuário diz só 'continua' ou 'não funcionou'."""
    docs = _DOCS if docs is None else docs
    do_usuario = [normalizar(m.get("content", "")) for m in mensagens if m.get("role") == "user"]
    if not do_usuario:
        return [d for d in docs if d.sempre]
    ultimo, anteriores = do_usuario[-1], " ".join(do_usuario[-3:-1])
    notas = []
    for d in docs:
        if d.sempre:
            continue
        n = 2 * pontuar(d, ultimo) + pontuar(d, anteriores)
        if n > 0:
            notas.append((n, d.nome, d))
    notas.sort(key=lambda x: (-x[0], x[1]))
    escolhidos, total = [d for d in docs if d.sempre], 0
    total = sum(len(d.texto) for d in escolhidos)
    extras = 0
    for _, _, d in notas:
        if extras >= MAX_DOCS or total + len(d.texto) > MAX_CARACTERES:
            continue
        escolhidos.append(d)
        total += len(d.texto)
        extras += 1
    return escolhidos


def como_texto(docs: list[Doc]) -> str:
    if not docs:
        return ""
    partes = [f"--- documento: {d.nome} ---\n{d.texto}" for d in docs]
    return ("DOCUMENTOS DO VISTA (receitas testadas: siga estes exemplos e esta API; não invente funções "
            "que não estão aqui nem na instrução):\n\n" + "\n\n".join(partes))
