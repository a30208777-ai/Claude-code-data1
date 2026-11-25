"""Registro de banimentos e punições do VISTA nos webhooks do Discord.

    Banimentos (ban, desban, IP bloqueado/desbloqueado) -> ROLOX_WEBHOOK_BANIMENTOS
    Punições (sem chat, chat liberado, aviso, denúncia) -> ROLOX_WEBHOOK_PUNICOES

Os links ficam no arquivo ~/.rolox.env (NUNCA no GitHub: quem tem o link posta no canal):

    ROLOX_WEBHOOK_BANIMENTOS=https://discord.com/api/webhooks/...
    ROLOX_WEBHOOK_PUNICOES=https://discord.com/api/webhooks/...

Este mesmo arquivo é usado pelo bot do Discord, pelo app Flet e pelo app Flask.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

# tipo -> (canal, título, cor)
TIPOS = {
    "ban": ("banimentos", "🔨 Banimento", 0xE53935),
    "desban": ("banimentos", "✅ Desbanimento", 0x43A047),
    "ip_bloqueado": ("banimentos", "🛡️ IP bloqueado", 0x8E24AA),
    "ip_desbloqueado": ("banimentos", "🔓 IP desbloqueado", 0x43A047),
    "sem_chat": ("punicoes", "🔇 Sem chat", 0xFB8C00),
    "com_chat": ("punicoes", "💬 Chat liberado", 0x1E88E5),
    "aviso": ("punicoes", "⚠️ Aviso", 0xFDD835),
    "denuncia": ("punicoes", "🚩 Denúncia", 0x8E24AA),
}
VARIAVEIS = {"banimentos": "ROLOX_WEBHOOK_BANIMENTOS", "punicoes": "ROLOX_WEBHOOK_PUNICOES"}
URL_VALIDA = re.compile(r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")


def carregar_env(caminhos: Optional[list] = None) -> Optional[Path]:
    """Lê ROLOX_*/DISCORD_* de ~/.rolox.env (ou ROLOX_ENV / ./.env) sem sobrescrever o ambiente."""
    candidatos = caminhos or [os.environ.get("ROLOX_ENV", ""), Path.home() / ".rolox.env", Path.cwd() / ".env"]
    for c in candidatos:
        if not c or not Path(c).is_file():
            continue
        for linha in Path(c).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.removeprefix("export ").split("=", 1)
            chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
            if chave.startswith(("ROLOX_", "DISCORD_")) and valor and chave not in os.environ:
                os.environ[chave] = valor
        return Path(c)
    return None


def url_do_canal(canal: str) -> Optional[str]:
    url = os.environ.get(VARIAVEIS[canal], "").strip()
    return url if URL_VALIDA.match(url) else None


def configurado() -> dict:
    return {canal: url_do_canal(canal) is not None for canal in VARIAVEIS}


def _texto(v, limite: int) -> str:
    t = str(v if v not in (None, "") else "—").replace("\r", "").strip()
    return t if len(t) <= limite else t[: limite - 1] + "…"


def formatar_duracao(minutos: int) -> str:
    if minutos % 1440 == 0:
        d = minutos // 1440
        return f"{d} dia{'s' if d > 1 else ''}"
    if minutos % 60 == 0:
        h = minutos // 60
        return f"{h} hora{'s' if h > 1 else ''}"
    return f"{minutos} minuto{'s' if minutos > 1 else ''}"


def montar_mensagem(tipo: str, alvo: str, motivo: str = "", por: str = "", onde: str = "Jogo VISTA",
                    duracao_min: Optional[int] = None, agora: Optional[datetime] = None) -> dict:
    """Corpo do webhook (um embed). Menções desligadas: ninguém é marcado pelo motivo."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconhecido: {tipo}")
    _, titulo, cor = TIPOS[tipo]
    agora = agora or datetime.now(timezone.utc)
    campos = [
        {"name": "Jogador" if onde.startswith("Jogo") else "Membro", "value": _texto(alvo, 256), "inline": True},
        {"name": "Por", "value": _texto(por or "sistema", 256), "inline": True},
        {"name": "Onde", "value": _texto(onde, 100), "inline": True},
    ]
    if duracao_min:
        fim = int((agora + timedelta(minutes=duracao_min)).timestamp())
        campos.append({"name": "Duração", "value": formatar_duracao(int(duracao_min)), "inline": True})
        campos.append({"name": "Até", "value": f"<t:{fim}:f> (<t:{fim}:R>)", "inline": True})
    campos.append({"name": "Motivo", "value": _texto(motivo or "sem motivo", 1000), "inline": False})
    return {
        "username": "VISTA Moderação",
        "allowed_mentions": {"parse": []},
        "embeds": [{"title": titulo, "color": cor, "fields": campos, "timestamp": agora.isoformat()}],
    }


async def registrar(tipo: str, alvo: str, motivo: str = "", por: str = "", onde: str = "Jogo VISTA",
                    duracao_min: Optional[int] = None, transport: Optional[httpx.AsyncBaseTransport] = None) -> bool:
    """Manda para o webhook certo. Devolve False se não configurado ou se o Discord recusou (nunca lança)."""
    url = url_do_canal(TIPOS[tipo][0]) if tipo in TIPOS else None
    if not url:
        return False
    corpo = montar_mensagem(tipo, alvo, motivo, por, onde, duracao_min)
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport) as c:
            for _ in range(2):
                r = await c.post(url, json=corpo)
                if r.status_code == 429:                       # limite do Discord: espera e tenta 1 vez
                    try:
                        espera = float(r.json().get("retry_after", 1))
                    except ValueError:
                        espera = 1.0
                    await asyncio.sleep(min(espera, 5))
                    continue
                return r.status_code in (200, 204)
    except httpx.HTTPError:
        return False
    return False


def registrar_sync(*args, transport: Optional[httpx.BaseTransport] = None, **kw) -> bool:
    """Versão síncrona (Flask)."""
    tipo = args[0] if args else kw.get("tipo")
    url = url_do_canal(TIPOS[tipo][0]) if tipo in TIPOS else None
    if not url:
        return False
    nomes = ["tipo", "alvo", "motivo", "por", "onde", "duracao_min"]
    dados = dict(zip(nomes, args)) | kw
    corpo = montar_mensagem(**dados)
    try:
        with httpx.Client(timeout=10, transport=transport) as c:
            r = c.post(url, json=corpo)
            return r.status_code in (200, 204)
    except httpx.HTTPError:
        return False
