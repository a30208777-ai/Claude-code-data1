"""Multijogador do ROLOX: posição de quem está no mesmo servidor de jogo.

Cada jogador manda o próprio estado (posição, giro, se está andando) umas 7x por
segundo e recebe o dos outros. A sala fica num arquivo JSON por servidor, com
trava (fcntl), para funcionar com vários processos do gunicorn na mesma máquina.

Quem pode estar numa sala é decidido UMA vez, ao abrir /jogar (o Supabase confirma
que o jogador está no servidor). Ele recebe um passe assinado com o segredo do site
(servidor, usuário, nome, avatar), e as atualizações só checam esse passe:
nada de Supabase a cada quadro.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer

SUMIU_APOS = 6.0            # segundos sem atualizar: sai da sala
MAX_JOGADORES = 100
LIMITE_COORD = 100_000.0
SALA_VALIDA = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class Passes:
    def __init__(self, segredo: str, validade_s: int = 8 * 3600):
        self.s = URLSafeTimedSerializer(segredo, salt="rolox-sala")
        self.validade = validade_s

    def criar(self, sala: str, user_id: str, nome: str, avatar: dict) -> str:
        return self.s.dumps({"s": sala, "u": user_id, "n": nome[:32], "a": avatar})

    def ler(self, passe: str) -> Optional[dict]:
        try:
            d = self.s.loads(passe, max_age=self.validade)
        except (BadSignature, TypeError, ValueError):
            return None
        return d if isinstance(d, dict) and SALA_VALIDA.match(str(d.get("s", ""))) else None


def _num(v, padrao=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return padrao
    if not math.isfinite(f):
        return padrao
    return max(-LIMITE_COORD, min(LIMITE_COORD, f))


def limpar_estado(d: dict) -> dict:
    """Só números finitos e limitados; nada que o jogador mande vira HTML ou código."""
    p = d.get("p") if isinstance(d.get("p"), list) else []
    p = (p + [0, 0, 0])[:3]
    return {"p": [round(_num(x), 3) for x in p], "r": round(_num(d.get("r")) % (2 * math.pi), 3),
            "m": bool(d.get("m")), "v": bool(d.get("v", True))}


class Salas:
    def __init__(self, pasta: Optional[Path] = None):
        self._pasta = Path(pasta) if pasta else None

    @property
    def pasta(self) -> Path:
        p = self._pasta or Path(os.environ.get("ROLOX_PASTA_SALAS") or Path(tempfile.gettempdir()) / "rolox-salas")
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _arquivo(self, sala: str) -> Path:
        if not SALA_VALIDA.match(sala):
            raise ValueError("sala inválida")
        return self.pasta / f"{sala}.json"

    def _com_trava(self, sala: str, mudar):
        arq = self._arquivo(sala)
        with open(arq, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                try:
                    dados = json.loads(f.read() or "{}")
                except ValueError:
                    dados = {}
                resultado = mudar(dados)
                f.seek(0)
                f.truncate()
                f.write(json.dumps(dados, separators=(",", ":")))
                return resultado
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def atualizar(self, passe: dict, estado: dict, agora: Optional[float] = None) -> list[dict]:
        """Grava o meu estado e devolve os OUTROS jogadores (sem os que sumiram)."""
        agora = agora if agora is not None else time.time()
        eu = passe["u"]

        def mudar(dados):
            for k in [k for k, v in dados.items() if agora - v.get("t", 0) > SUMIU_APOS]:
                dados.pop(k)
            if eu in dados or len(dados) < MAX_JOGADORES:
                dados[eu] = {"n": passe["n"], "a": passe.get("a") or {}, **limpar_estado(estado), "t": agora}
            return [{"id": k, **{c: v[c] for c in ("n", "a", "p", "r", "m", "v")}}
                    for k, v in dados.items() if k != eu]
        return self._com_trava(passe["s"], mudar)

    def sair(self, passe: dict) -> None:
        self._com_trava(passe["s"], lambda dados: dados.pop(passe["u"], None))
