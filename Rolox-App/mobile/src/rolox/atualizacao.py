"""O ROLOX confere se tem versão nova e prova que é o app oficial.

Lê o mesmo arquivo que o Atualizador do ROLOX usa:
  https://raw.githubusercontent.com/a30208777-ai/Rolox-apk/refs/heads/main/Vision-apk-link.json
  { "version": 0.20 ; "link": "https://..." ; "proctetion": "..." }
- version: se for maior que a versão deste app, o ROLOX pede para atualizar (pelo Atualizador).
- proctetion: a chave do app oficial. O ROLOX manda ao servidor; se o dono cadastrou essa chave
  (Dono -> ✅ App oficial), a conta ganha ✅; senão fica ❌ (app modificado).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx

VERSAO_APP = "0.27.0"          # igual ao version do pyproject.toml (um teste confere)
URL_INFO = "https://raw.githubusercontent.com/a30208777-ai/Rolox-apk/refs/heads/main/Vision-apk-link.json"
LINK_ATUALIZADOR = "roloxatualizador://atualizar"
MAX_INFO = 64 * 1024


@dataclass
class InfoVersao:
    versao: str
    link: str
    protecao: str


def _campo(texto: str, *nomes: str) -> Optional[str]:
    for nome in nomes:
        m = re.search(r'"%s"\s*:\s*("((?:[^"\\]|\\.)*)"|[0-9][0-9.]*)' % re.escape(nome), texto)
        if m:
            return m.group(2) if m.group(2) is not None else m.group(1)
    return None


def ler_info(texto: str) -> Optional[InfoVersao]:
    """Lê o arquivo (aceita ';' no lugar de ','; '0.20' continua '0.20'). None se estiver estranho."""
    versao = _campo(texto, "version", "versao")
    link = (_campo(texto, "link", "url") or "").replace("\\/", "/").strip()
    protecao = _campo(texto, "proctetion", "protection", "protecao") or ""
    if not versao or not re.fullmatch(r"\d+(\.\d+)*", versao.strip()):
        return None
    return InfoVersao(versao.strip(), link, protecao)


def chave_versao(v: Optional[str]) -> tuple:
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except (TypeError, ValueError):
        return ()


def tem_versao_nova(online: Optional[str], minha: str = VERSAO_APP) -> bool:
    """'0.20' vs '0.24.0': compara número por número (faltando conta como 0)."""
    a, b = list(chave_versao(online)), list(chave_versao(minha))
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + [0] * (n - len(a)) > b + [0] * (n - len(b))


async def buscar_info(cliente: Optional[httpx.AsyncClient] = None) -> Optional[InfoVersao]:
    """None se não deu para ler (sem internet, arquivo fora do ar): o ROLOX segue normal."""
    dono = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=10, follow_redirects=True)
    try:
        r = await cliente.get(URL_INFO, headers={"Cache-Control": "no-cache"})
        if r.status_code != 200 or len(r.content) > MAX_INFO:
            return None
        return ler_info(r.text)
    except httpx.HTTPError:
        return None
    finally:
        if dono:
            await cliente.aclose()


def marca_app(perfil: dict) -> str:
    """' ✅' (app oficial, últimos 7 dias), ' ❌' (app modificado) ou '' — para pôr depois do nome."""
    from datetime import datetime, timedelta
    st = perfil.get("app_status") or perfil.get("app")
    if st == "modificado":
        return " ❌"
    if st == "oficial":
        quando = perfil.get("app_verificado_em")
        if quando is None and perfil.get("app") == "oficial":      # já veio julgado pelo servidor
            return " ✅"
        try:
            t = datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
            if datetime.now(t.tzinfo) - t < timedelta(days=7):
                return " ✅"
        except ValueError:
            pass
    return ""
