import asyncio
from types import SimpleNamespace

import flet as ft

from rolox import protecao


def test_avisos_por_quantidade_de_vezes():
    assert protecao.aviso_para(1) == ("Ei!, abaixou uma cópia pirata?", "Enfim, entre no nosso Discord e abaixe o app.", False)
    assert protecao.aviso_para(2)[2] is False
    titulo, texto, serio = protecao.aviso_para(3)
    assert serio and titulo == "EI! VOCÊ PODE SER BANIDO!" and texto.startswith("ABAIXE O APP POR:")
    assert protecao.aviso_para(10)[2] is True
    assert protecao.LINK_DISCORD == "https://discord.gg/qWRyzSYzRV"


def test_contador_e_por_usuario():
    assert protecao.chave_contador("Alice") == "rolox.sem_atualizador.alice"
    assert protecao.chave_contador(None) == "rolox.sem_atualizador.aparelho"
    assert protecao.chave_contador("a b/../c") == "rolox.sem_atualizador.ab..c"


def test_so_exige_o_atualizador_no_android(monkeypatch):
    pc = SimpleNamespace(platform=ft.PagePlatform.WINDOWS)
    assert asyncio.run(protecao.atualizador_instalado(pc)) is True

    class Lancador:
        resposta = False
        async def can_launch_url(self, url):
            assert url == "roloxatualizador://verificar"
            return Lancador.resposta
    monkeypatch.setattr(ft, "UrlLauncher", Lancador)
    android = SimpleNamespace(platform=ft.PagePlatform.ANDROID)
    assert asyncio.run(protecao.atualizador_instalado(android)) is False
    Lancador.resposta = True
    assert asyncio.run(protecao.atualizador_instalado(android)) is True
