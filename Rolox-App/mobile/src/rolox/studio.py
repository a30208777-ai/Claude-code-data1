"""Ligação do app com o Vista Studio (o editor de jogos que roda no aparelho).

O Studio é o servidor de `Rolox-Studio/servidor.py` (padrão: http://localhost:8600).
Ele só responde ao próprio aparelho, então o app e o Studio precisam estar no
mesmo celular/PC (no Termux: uma sessão com o app e outra com o Studio).
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlencode

import httpx

from . import config

NOME_PROJETO = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

MODOS = {"leve": "Studio leve (celular)", "pc": "Studio PC"}

MODELOS = [
    ("vazio", "Vazio", "Chão e ponto de nascimento."),
    ("obby", "Obby (parkour)", "Plataformas sobre lava, checkpoint e cronômetro (Luau)."),
    ("moedas", "Coleta de moedas", "Moedas que giram e contam pontos (Python)."),
]

COMANDO_LIGAR = "cd Claude-code-data1/Rolox-Studio && python servidor.py"


class StudioLocal:
    def __init__(self, base: str = config.STUDIO_URL, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base = base.rstrip("/")
        self.transport = transport

    def url(self, modo: str = "leve", projeto: Optional[str] = None, modelo: Optional[str] = None) -> str:
        """Endereço para abrir o Studio (opcionalmente já com um projeto ou um modelo)."""
        if modo not in MODOS:
            raise ValueError(f"modo inválido: {modo}")
        params = {}
        if projeto:
            if not NOME_PROJETO.match(projeto):
                raise ValueError("nome de projeto inválido")
            params["projeto"] = projeto
        elif modelo:
            if modelo not in {m[0] for m in MODELOS}:
                raise ValueError("modelo inválido")
            params["modelo"] = modelo
        return f"{self.base}/studio/{modo}" + (f"?{urlencode(params)}" if params else "")

    def _cliente(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base, timeout=timeout, transport=self.transport)

    async def ligado(self) -> bool:
        """True se o servidor do Studio responde neste aparelho."""
        try:
            async with self._cliente(2) as c:
                r = await c.get("/")
            return r.status_code == 200 and "Vista Studio".lower() in r.text.lower()
        except httpx.HTTPError:
            return False

    async def projetos(self) -> list[dict]:
        """Projetos salvos no Studio: [{"nome", "tamanho"}], do mais recente para o mais antigo."""
        try:
            async with self._cliente(4) as c:
                r = await c.get("/api/projetos")
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        try:
            dados = r.json()
        except ValueError:
            return []
        return [p for p in dados if isinstance(p, dict) and NOME_PROJETO.match(str(p.get("nome", "")))]
