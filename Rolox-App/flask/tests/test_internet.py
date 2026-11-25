"""Internet do VISTA (pesquisa segura pelo servidor), sem internet de verdade."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import internet  # noqa: E402


class R:
    def __init__(self, status, corpo):
        self.status_code, self._c = status, corpo

    def json(self):
        return self._c


class Http:
    def __init__(self):
        self.pedidos = []

    def get(self, url, timeout, headers, params):
        self.pedidos.append((url, params, headers))
        if "duckduckgo" in url:
            return R(200, {"Heading": "Dinossauro", "AbstractText": "Répteis que dominaram a Terra.",
                           "AbstractURL": "https://pt.wikipedia.org/wiki/Dinossauro",
                           "RelatedTopics": [{"Text": "T-Rex - um dinossauro carnívoro", "FirstURL": "https://duckduckgo.com/T-Rex"},
                                             {"Text": "golpe", "FirstURL": "javascript:alert(1)"}]})
        return R(200, {"query": {"search": [{"title": "Dinossauro", "snippet": "<span class=\"searchmatch\">Dino</span>ssauros &amp; aves"},
                                            {"title": "Fósseis", "snippet": "restos de seres"}]}})


@pytest.fixture(autouse=True)
def limpar():
    internet._cache.clear()
    internet._uso.clear()


def test_pesquisa_junta_fontes_sem_html_sem_repetir():
    http = Http()
    r = internet.pesquisar("  dinossauros  ", "u1", http=http)
    titulos = [x["titulo"] for x in r]
    assert titulos == ["Dinossauro", "T-Rex", "Fósseis"]                  # "Dinossauro" da Wikipédia não repete
    assert all("<" not in x["resumo"] for x in r)
    assert all(x["link"].startswith("https://") for x in r)              # javascript: fica de fora
    url, params, cab = http.pedidos[0]
    assert params["kp"] == 1 and "VISTA" in cab["User-Agent"]             # busca segura, sem dados de ninguém
    assert internet.como_texto(r).startswith("Dinossauro: Répteis")


def test_cache_e_limite_por_minuto():
    http = Http()
    t = [1000.0]
    internet.pesquisar("gatos", "u1", http=http, agora=lambda: t[0])
    internet.pesquisar("gatos", "u1", http=http, agora=lambda: t[0])
    assert len(http.pedidos) == 2                                          # 2ª vez veio do cache (2 fontes, 1 vez)
    for _ in range(internet.LIMITE_MINUTO - 2):
        internet.pesquisar("gatos", "u1", http=http, agora=lambda: t[0])
    with pytest.raises(internet.ErroInternet) as e:
        internet.pesquisar("gatos", "u1", http=http, agora=lambda: t[0])
    assert e.value.codigo == "muitas_pesquisas"
    t[0] += 61
    internet.pesquisar("gatos", "u1", http=http, agora=lambda: t[0])        # passou 1 minuto: libera


def test_termos_curtos_e_bloqueados():
    for ruim in ("a", "  ", "porno grátis", "como fazer bomba caseira"):
        with pytest.raises(internet.ErroInternet):
            internet.pesquisar(ruim, "u1", http=Http())


def test_fonte_fora_do_ar_nao_quebra():
    class Falha(Http):
        def get(self, url, **k):
            if "duckduckgo" in url:
                import requests
                raise requests.ConnectionError("caiu")
            return super().get(url, **k)
    r = internet.pesquisar("fosseis", "u1", http=Falha())
    assert [x["fonte"] for x in r] == ["Wikipédia", "Wikipédia"]
