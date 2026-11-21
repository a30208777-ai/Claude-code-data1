"""Baixar e extrair o ROLOX (sem nada de Android aqui: dá para testar no PC).

O dono publica no GitHub (repositório a30208777-ai/Rolox-apk) o arquivo Vision-apk-link.json com
a versão nova e o link de download. O Atualizador lê esse arquivo, compara a versão e baixa pelo
link: se o link entregar o .apk (ou um .zip com ele), instala; se for uma página de download
(ex.: TransferNow), abre no navegador.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

import httpx

REPO = "a30208777-ai/Rolox-apk"
# arquivo que diz qual é a versão nova do ROLOX e onde baixar (o dono edita no GitHub)
URL_INFO = f"https://raw.githubusercontent.com/{REPO}/refs/heads/main/Vision-apk-link.json"
AGENTE = "AtualizadorROLOX/1.0"
MAX_ZIP = 400 * 1024 * 1024          # 400 MB: mais que isso não é o ROLOX
MAX_INFO = 64 * 1024
PRAZO = httpx.Timeout(30.0, read=60.0)


class ErroAtualizador(Exception):
    """Erro com mensagem para mostrar ao jogador."""


class PrecisaNavegador(Exception):
    """O link é uma página de download (ex.: TransferNow), não o arquivo: abrir no navegador."""


@dataclass
class Baixado:
    apk: Path
    tamanho: int
    sha256: str
    nome_original: str


@dataclass
class InfoVersao:
    versao: str          # como está escrito no arquivo ("0.20" continua "0.20", não vira 0.2)
    link: str
    protecao: str


def _campo(texto: str, *nomes: str) -> Optional[str]:
    """Valor de "nome": ... mesmo com o arquivo fora do padrão JSON (ex.: ';' no lugar de ',')."""
    for nome in nomes:
        m = re.search(r'"%s"\s*:\s*("((?:[^"\\]|\\.)*)"|[0-9][0-9.]*)' % re.escape(nome), texto)
        if m:
            return m.group(2) if m.group(2) is not None else m.group(1)
    return None


def ler_info(texto: str) -> InfoVersao:
    """Lê o Vision-apk-link.json. Aceita JSON certinho e também o jeito que o dono escreveu
    (com ';' no fim das linhas). A versão é lida como TEXTO para 0.20 não virar 0.2."""
    versao = _campo(texto, "version", "versao", "versão")
    link = _campo(texto, "link", "url")
    protecao = _campo(texto, "proctetion", "protection", "protecao", "proteção") or ""
    if not versao or not re.fullmatch(r"\d+(\.\d+)*", versao.strip()):
        raise ErroAtualizador("O arquivo de versão do ROLOX está sem a versão (version).")
    link = (link or "").replace("\\/", "/").strip()
    if not link.startswith("https://"):
        raise ErroAtualizador("O arquivo de versão do ROLOX está sem um link https de download.")
    return InfoVersao(versao.strip(), link, protecao)


def chave_versao(v: Optional[str]) -> tuple:
    """'0.20' -> (0, 20): compara versões como números (0.20 é mais nova que 0.9)."""
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except (TypeError, ValueError):
        return ()


def eh_mais_nova(online: Optional[str], instalada: Optional[str]) -> bool:
    return bool(online) and (not instalada or chave_versao(online) > chave_versao(instalada))


async def buscar_info(cliente: Optional[httpx.AsyncClient] = None) -> InfoVersao:
    """Baixa e lê o arquivo de versão do GitHub."""
    dono = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=PRAZO, follow_redirects=True, headers={"User-Agent": AGENTE})
    try:
        r = await cliente.get(URL_INFO, headers={"Cache-Control": "no-cache"})
        if r.status_code == 404:
            raise ErroAtualizador("Ainda não tem versão do ROLOX publicada.")
        if r.status_code != 200:
            raise ErroAtualizador(f"O GitHub respondeu {r.status_code}. Tente de novo daqui a pouco.")
        if len(r.content) > MAX_INFO:
            raise ErroAtualizador("O arquivo de versão do ROLOX está estranho (grande demais).")
        return ler_info(r.text)
    except httpx.HTTPError as e:
        raise ErroAtualizador("Sem internet ou o GitHub não respondeu. Confira a conexão.") from e
    finally:
        if dono:
            await cliente.aclose()


async def baixar_arquivo(link: str, progresso: Callable[[int, Optional[int]], None] = lambda feito, total: None,
                         cliente: Optional[httpx.AsyncClient] = None) -> bytes:
    """Baixa o que o link entregar. Se for uma PÁGINA (site de transferência), levanta PrecisaNavegador."""
    dono = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=PRAZO, follow_redirects=True, headers={"User-Agent": AGENTE})
    try:
        async with cliente.stream("GET", link) as r:
            if r.status_code == 404:
                raise ErroAtualizador("O link de download do ROLOX não existe mais. Avise no Discord.")
            if r.status_code != 200:
                raise ErroAtualizador(f"O site do download respondeu {r.status_code}. Tente de novo daqui a pouco.")
            tipo = r.headers.get("content-type", "").lower()
            if "text/html" in tipo or "json" in tipo:
                raise PrecisaNavegador(link)
            total = int(r.headers.get("content-length") or 0) or None
            if total and total > MAX_ZIP:
                raise ErroAtualizador("O arquivo do ROLOX está grande demais.")
            buf = io.BytesIO()
            async for parte in r.aiter_bytes():
                if buf.tell() == 0 and not parte.startswith(b"PK"):
                    raise PrecisaNavegador(link)          # não é .apk nem .zip: é uma página
                buf.write(parte)
                if buf.tell() > MAX_ZIP:
                    raise ErroAtualizador("O arquivo do ROLOX está grande demais.")
                progresso(buf.tell(), total)
            return buf.getvalue()
    except httpx.HTTPError as e:
        raise ErroAtualizador("Sem internet ou o site do download não respondeu. Confira a conexão.") from e
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
        nomes = z.namelist()
        if "AndroidManifest.xml" in nomes:          # o link já era o .apk (não um .zip com o .apk)
            dados = dados_zip
            return _salvar(dados, pasta, "ROLOX.apk")
        escolhido = escolher_apk(nomes)
        if not escolhido:
            raise ErroAtualizador("Não achei o app do ROLOX (.apk) no pacote baixado.")
        info = z.getinfo(escolhido)
        if info.file_size > MAX_ZIP:
            raise ErroAtualizador("O app do ROLOX está grande demais.")
        dados = z.read(escolhido)
    if dados[:2] != b"PK":                      # um .apk é um zip por dentro
        raise ErroAtualizador("O arquivo do ROLOX não parece um app Android válido.")
    return _salvar(dados, pasta, PurePosixPath(escolhido).name)


def _salvar(dados: bytes, pasta: Path, nome_original: str) -> Baixado:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "rolox.apk"
    temporario = pasta / "rolox.apk.parte"
    temporario.write_bytes(dados)
    temporario.replace(destino)
    return Baixado(destino, len(dados), hashlib.sha256(dados).hexdigest(), nome_original)


def tamanho_legivel(n: Optional[int]) -> str:
    if n is None:
        return "?"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"
