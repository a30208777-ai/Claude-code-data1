"""Internet no VISTA: pesquisas feitas pelo SERVIDOR (o Render), só em fontes seguras.

Os jogos (serviço Internet) e os jogadores (Buscar → 🌐 Internet) mandam um termo; o site
pesquisa na Wikipédia em português e nas respostas rápidas do DuckDuckGo (busca segura no
máximo) e devolve só TEXTO: título, resumo e link. Nunca abre endereço que o jogo escolher
(isso evita usar o servidor para atacar outros sites ou buscar conteúdo impróprio).

Limites: termo de 2 a 100 letras, 20 pesquisas por minuto por jogador, respostas guardadas
por 10 minutos, 6 s de espera por fonte.
"""

from __future__ import annotations

import html
import re
import threading
import time
from typing import Optional

import requests

AGENTE = "VISTA/1.0 (plataforma de jogos; pesquisa segura)"   # sem dados de ninguém
PRAZO = 6
CACHE_S = 600
LIMITE_MINUTO = 20
MAX_RESULTADOS = 6

_cache: dict = {}                 # termo -> (quando, resultados)
_uso: dict = {}                   # user -> [instantes]
_trava = threading.Lock()

# palavras que fazem a pesquisa ser recusada (plataforma para todas as idades)
BLOQUEADAS = re.compile(r"\b(porn\w*|sexo|xxx|nud[ea]s?|hentai|onlyfans|droga[s]?|coca[ií]na|maconha|suic[ií]dio|"
                        r"arma[s]? caseira|bomba caseira)\b", re.I)


class ErroInternet(Exception):
    def __init__(self, codigo: str, mensagem: str):
        super().__init__(codigo)
        self.codigo, self.mensagem = codigo, mensagem


def limpar_termo(termo: str) -> str:
    t = re.sub(r"\s+", " ", str(termo or "")).strip()[:100]
    if len(t) < 2:
        raise ErroInternet("termo_curto", "Digite pelo menos 2 letras para pesquisar.")
    if BLOQUEADAS.search(t):
        raise ErroInternet("termo_bloqueado", "Essa pesquisa não é permitida no VISTA.")
    return t


def _sem_html(texto: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(texto or ""))).strip()


def _wikipedia(termo: str, http) -> list[dict]:
    r = http.get("https://pt.wikipedia.org/w/api.php", timeout=PRAZO, headers={"User-Agent": AGENTE}, params={
        "action": "query", "list": "search", "srsearch": termo, "format": "json", "srlimit": 4, "utf8": 1})
    if r.status_code != 200:
        return []
    saida = []
    for it in (r.json().get("query") or {}).get("search", [])[:4]:
        titulo = _sem_html(it.get("title"))
        if titulo:
            saida.append({"titulo": titulo, "resumo": _sem_html(it.get("snippet"))[:300] + "…",
                          "link": "https://pt.wikipedia.org/wiki/" + requests.utils.quote(titulo.replace(" ", "_")),
                          "fonte": "Wikipédia"})
    return saida


def _duckduckgo(termo: str, http) -> list[dict]:
    r = http.get("https://api.duckduckgo.com/", timeout=PRAZO, headers={"User-Agent": AGENTE}, params={
        "q": termo, "format": "json", "no_html": 1, "skip_disambig": 1, "kp": 1, "kl": "br-pt"})
    if r.status_code != 200:
        return []
    d = r.json()
    saida = []
    if d.get("AbstractText"):
        saida.append({"titulo": _sem_html(d.get("Heading") or termo), "resumo": _sem_html(d["AbstractText"])[:300],
                      "link": d.get("AbstractURL") or "", "fonte": "DuckDuckGo"})
    for t in (d.get("RelatedTopics") or [])[:3]:
        if isinstance(t, dict) and t.get("Text") and str(t.get("FirstURL", "")).startswith("https://"):
            saida.append({"titulo": _sem_html(t["Text"]).split(" - ")[0][:80], "resumo": _sem_html(t["Text"])[:300],
                          "link": t["FirstURL"], "fonte": "DuckDuckGo"})
    return saida


def pesquisar(termo: str, usuario: str = "", http=requests, agora=time.monotonic) -> list[dict]:
    t = limpar_termo(termo)
    chave = t.lower()
    with _trava:
        if usuario:
            janela = [x for x in _uso.get(usuario, []) if agora() - x < 60]
            if len(janela) >= LIMITE_MINUTO:
                raise ErroInternet("muitas_pesquisas", "Muitas pesquisas seguidas. Espere um minuto.")
            janela.append(agora())
            _uso[usuario] = janela
        em_cache: Optional[tuple] = _cache.get(chave)
        if em_cache and agora() - em_cache[0] < CACHE_S:
            return em_cache[1]
    resultados: list[dict] = []
    for fonte in (_duckduckgo, _wikipedia):
        try:
            resultados += fonte(t, http)
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            continue
    vistos, unicos = set(), []
    for r in resultados:
        if r["titulo"].lower() not in vistos and not BLOQUEADAS.search(r["titulo"] + " " + r["resumo"]):
            vistos.add(r["titulo"].lower())
            unicos.append(r)
    unicos = unicos[:MAX_RESULTADOS]
    with _trava:
        if len(_cache) > 500:
            _cache.clear()
        _cache[chave] = (agora(), unicos)
    return unicos


def como_texto(resultados: list[dict], maximo: int = 3) -> str:
    """Para os scripts: 'Título: resumo' dos primeiros resultados, uma linha cada."""
    return "\n".join(f"{r['titulo']}: {r['resumo']}" for r in resultados[:maximo]) or "Nada encontrado."
