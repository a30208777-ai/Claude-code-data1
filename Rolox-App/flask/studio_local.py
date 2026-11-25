"""Ligação do Vista Flask com o VISTA Studio (o editor de jogos que roda no aparelho).

O Studio é o servidor de `Rolox-Studio/servidor.py` (padrão: http://localhost:8600).
Ele só responde ao próprio aparelho, então este app e o Studio precisam estar no
mesmo celular/PC (no Termux: uma sessão com este app e outra com o Studio).

Mesma lógica de `Rolox-App/mobile/src/rolox/studio.py`, mas síncrona (requests).
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional
from urllib.parse import urlencode

import requests

STUDIO_URL = os.environ.get("ROLOX_STUDIO_URL", "http://localhost:8600")

NOME_PROJETO = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

MODOS = {"leve": "Studio leve (celular)", "pc": "Studio PC"}

MODELOS = [
    ("vazio", "Vazio", "Chão e ponto de nascimento."),
    ("obby", "Obby (parkour)", "Plataformas sobre lava, checkpoint e cronômetro (Luau)."),
    ("moedas", "Coleta de moedas", "Moedas que giram e contam pontos (Python)."),
]

COMANDO_LIGAR = "cd Claude-code-data1/Rolox-Studio && python servidor.py"
COMANDO_INSTALAR = "pip install -r requirements.txt"


class StudioLocal:
    def __init__(self, base: str = STUDIO_URL, http: Any = None):
        self.base = base.rstrip("/")
        self.http = http or requests        # nos testes: um objeto falso com .get()

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

    def _get(self, caminho: str, timeout: float):
        try:
            return self.http.get(self.base + caminho, timeout=timeout)
        except requests.RequestException:
            return None

    def ligado(self) -> bool:
        """True se o servidor do Studio responde neste aparelho."""
        r = self._get("/", 2)
        return r is not None and r.status_code == 200 and any(n in (r.text or "").lower() for n in ("vista studio", "rolox studio"))

    def projetos(self) -> list[dict]:
        """Projetos salvos no Studio: [{"nome", "tamanho"}], do mais recente para o mais antigo."""
        r = self._get("/api/projetos", 4)
        if r is None or r.status_code != 200:
            return []
        try:
            dados = r.json()
        except ValueError:
            return []
        if not isinstance(dados, list):
            return []
        return [p for p in dados if isinstance(p, dict) and NOME_PROJETO.match(str(p.get("nome", "")))]

    def tamanho_kb(self, p: dict) -> int:
        try:
            return max(1, round(int(p.get("tamanho", 0)) / 1024))
        except (TypeError, ValueError):
            return 1
