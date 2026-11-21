"""Baixar e extrair o ROLOX (sem nada de Android aqui: dá para testar no PC).

O ROLOX publicado fica no GitHub, no repositório a30208777-ai/Rolox-apk. O Atualizador baixa o
.zip do repositório, procura o .apk do ROLOX dentro dele e guarda só esse arquivo.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

import httpx

REPO = "a30208777-ai/Rolox-apk"
URL_ZIP = f"https://github.com/{REPO}/archive/refs/heads/main.zip"
URL_VERSAO = f"https://api.github.com/repos/{REPO}/commits/main"
AGENTE = "AtualizadorROLOX/1.0"
MAX_ZIP = 400 * 1024 * 1024          # 400 MB: mais que isso não é o ROLOX
PRAZO = httpx.Timeout(30.0, read=60.0)


class ErroAtualizador(Exception):
    """Erro com mensagem para mostrar ao jogador."""


@dataclass
class Baixado:
    apk: Path
    tamanho: int
    sha256: str
    nome_original: str


async def versao_online(cliente: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """Código (commit) da versão mais nova publicada, ou None se não deu para saber."""
    dono = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=PRAZO, headers={"User-Agent": AGENTE})
    try:
        r = await cliente.get(URL_VERSAO, headers={"Accept": "application/vnd.github.sha", "User-Agent": AGENTE})
        if r.status_code != 200:
            return None
        sha = r.text.strip()
        return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else None
    except httpx.HTTPError:
        return None
    finally:
        if dono:
            await cliente.aclose()


async def baixar_zip(progresso: Callable[[int, Optional[int]], None] = lambda feito, total: None,
                     cliente: Optional[httpx.AsyncClient] = None) -> bytes:
    """Baixa o .zip do repositório. `progresso(bytes_baixados, total_ou_None)`."""
    dono = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=PRAZO, follow_redirects=True, headers={"User-Agent": AGENTE})
    try:
        async with cliente.stream("GET", URL_ZIP) as r:
            if r.status_code == 404:
                raise ErroAtualizador("Ainda não tem versão do ROLOX publicada para baixar.")
            if r.status_code != 200:
                raise ErroAtualizador(f"O GitHub respondeu {r.status_code}. Tente de novo daqui a pouco.")
            total = int(r.headers.get("content-length") or 0) or None
            if total and total > MAX_ZIP:
                raise ErroAtualizador("O arquivo do ROLOX está grande demais.")
            buf = io.BytesIO()
            async for parte in r.aiter_bytes():
                buf.write(parte)
                if buf.tell() > MAX_ZIP:
                    raise ErroAtualizador("O arquivo do ROLOX está grande demais.")
                progresso(buf.tell(), total)
            return buf.getvalue()
    except httpx.HTTPError as e:
        raise ErroAtualizador("Sem internet ou o GitHub não respondeu. Confira a conexão.") from e
    finally:
        if dono:
            await cliente.aclose()


def escolher_apk(nomes: list[str]) -> Optional[str]:
    """O .apk do ROLOX dentro do zip: o que tem 'rolox' no nome (e não é o atualizador); senão o único."""
    apks = [n for n in nomes if n.lower().endswith(".apk") and not n.endswith("/")]
    if not apks:
        return None
    def nome(n): return PurePosixPath(n).name.lower()
    do_rolox = [n for n in apks if "rolox" in nome(n) and "atualizador" not in nome(n)]
    candidatos = do_rolox or [n for n in apks if "atualizador" not in nome(n)] or apks
    # se tiver mais de um, fica o de nome "maior" (ROLOX-0.1.40.apk > ROLOX-0.1.9.apk pela versão)
    def chave(n):
        partes = []
        for pedaco in nome(n).replace("-", ".").replace("_", ".").split("."):
            partes.append((1, int(pedaco), "") if pedaco.isdigit() else (0, 0, pedaco))
        return partes
    return max(candidatos, key=chave)


def extrair_apk(dados_zip: bytes, pasta: Path) -> Baixado:
    """Tira o .apk do ROLOX do zip e salva em `pasta/rolox.apk` (só ele: nada de extrair o zip todo)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(dados_zip))
    except zipfile.BadZipFile as e:
        raise ErroAtualizador("O arquivo baixado veio estragado. Tente de novo.") from e
    with z:
        escolhido = escolher_apk(z.namelist())
        if not escolhido:
            raise ErroAtualizador("Não achei o app do ROLOX (.apk) no pacote baixado.")
        info = z.getinfo(escolhido)
        if info.file_size > MAX_ZIP:
            raise ErroAtualizador("O app do ROLOX está grande demais.")
        dados = z.read(escolhido)
    if dados[:2] != b"PK":                      # um .apk é um zip por dentro
        raise ErroAtualizador("O arquivo do ROLOX não parece um app Android válido.")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "rolox.apk"
    temporario = pasta / "rolox.apk.parte"
    temporario.write_bytes(dados)
    temporario.replace(destino)
    return Baixado(destino, len(dados), hashlib.sha256(dados).hexdigest(), PurePosixPath(escolhido).name)


def tamanho_legivel(n: Optional[int]) -> str:
    if n is None:
        return "?"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"
