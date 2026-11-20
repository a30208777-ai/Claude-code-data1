"""Lê o ROLOX_DISCORD.md e acha a resposta certa para uma mensagem.

Formato aceito (as duas versões do arquivo):
    ### !comando                      ou   ### Pergunta
    Palavras: a, b, c                       Palavras-chave: a, b
                                            Comando: !comando
    texto da resposta...
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Resposta:
    titulo: str
    comando: str | None
    palavras: list[str] = field(default_factory=list)
    texto: str = ""


def ler_respostas(caminho: str | Path) -> list[Resposta]:
    md = Path(caminho).read_text(encoding="utf-8")
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    respostas = []
    for bloco in re.split(r"^### ", md, flags=re.M)[1:]:
        bloco = re.split(r"^## ", bloco, flags=re.M)[0]
        linhas = bloco.strip("\n").split("\n")
        titulo = linhas[0].strip()
        comando = titulo if titulo.startswith("!") else None
        palavras, corpo = [], []
        for linha in linhas[1:]:
            m = re.match(r"^(Palavras(?:-chave)?|Comando):\s*(.*)$", linha.strip())
            if m and not corpo:
                if m.group(1) == "Comando":
                    comando = m.group(2).strip()
                else:
                    palavras = [normalizar(p) for p in m.group(2).split(",") if p.strip()]
                continue
            corpo.append(linha)
        texto = "\n".join(corpo).strip()
        if texto:
            respostas.append(Resposta(titulo, comando.lower() if comando else None, palavras, texto[:2000]))
    return respostas


class Respostas:
    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.lista = ler_respostas(self.caminho)

    def recarregar(self) -> int:
        self.lista = ler_respostas(self.caminho)
        return len(self.lista)

    def por_comando(self, mensagem: str) -> Resposta | None:
        """'!studio abrir' casa com '!studio abrir' antes de '!studio'."""
        m = normalizar(mensagem)
        candidatas = [r for r in self.lista if r.comando and (m == normalizar(r.comando) or m.startswith(normalizar(r.comando) + " "))]
        return max(candidatas, key=lambda r: len(r.comando), default=None)

    def por_palavras(self, mensagem: str) -> Resposta | None:
        """A resposta com mais palavras-chave na mensagem (palavras inteiras)."""
        m = f" {re.sub(r'[^a-z0-9_ ]', ' ', normalizar(mensagem))} "
        m = re.sub(r"\s+", " ", m)
        melhor, pontos = None, 0
        for r in self.lista:
            p = sum(1 for k in r.palavras if k and f" {re.sub(r'[^a-z0-9_ ]', ' ', k).strip()} " in m)
            if p > pontos:
                melhor, pontos = r, p
        return melhor

    def comandos(self) -> list[str]:
        return [r.comando for r in self.lista if r.comando]
