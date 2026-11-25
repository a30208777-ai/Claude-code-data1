"""Testes da ligação do app com o Vista Studio (sem rede)."""

import asyncio

import httpx
import pytest

from rolox.studio import StudioLocal


def studio_com(handler) -> StudioLocal:
    return StudioLocal("http://localhost:8600", transport=httpx.MockTransport(handler))


def test_enderecos_do_studio():
    s = StudioLocal("http://localhost:8600/")
    assert s.url() == "http://localhost:8600/studio/leve"
    assert s.url("pc") == "http://localhost:8600/studio/pc"
    assert s.url("leve", projeto="meu-jogo") == "http://localhost:8600/studio/leve?projeto=meu-jogo"
    assert s.url("leve", modelo="obby") == "http://localhost:8600/studio/leve?modelo=obby"


@pytest.mark.parametrize("kw", [{"modo": "outro"}, {"projeto": "../x"}, {"projeto": "a b"}, {"modelo": "hack"}])
def test_enderecos_invalidos(kw):
    with pytest.raises(ValueError):
        StudioLocal().url(**kw)


def test_ligado_quando_o_studio_responde():
    s = studio_com(lambda r: httpx.Response(200, text="<h1>VISTA Studio</h1>"))
    assert asyncio.run(s.ligado()) is True


def test_desligado_quando_nao_responde_ou_e_outra_coisa():
    def sem_rede(req):
        raise httpx.ConnectError("recusado", request=req)

    assert asyncio.run(studio_com(sem_rede).ligado()) is False
    assert asyncio.run(studio_com(lambda r: httpx.Response(200, text="outro site")).ligado()) is False


def test_lista_projetos_e_ignora_nomes_estranhos():
    def h(req):
        assert req.url.path == "/api/projetos"
        return httpx.Response(200, json=[{"nome": "obby-da-bia", "tamanho": 2048}, {"nome": "../etc"}, "lixo"])

    assert asyncio.run(studio_com(h).projetos()) == [{"nome": "obby-da-bia", "tamanho": 2048}]


def test_projetos_vazio_se_der_erro():
    assert asyncio.run(studio_com(lambda r: httpx.Response(403)).projetos()) == []
    assert asyncio.run(studio_com(lambda r: httpx.Response(200, text="não é json")).projetos()) == []
