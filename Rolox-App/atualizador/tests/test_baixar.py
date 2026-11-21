import asyncio
import io
import tomllib
import zipfile
from pathlib import Path

import httpx
import pytest

from atualizador import android
from atualizador.baixar import (URL_INFO, ErroAtualizador, PrecisaNavegador, baixar_arquivo, buscar_info,
                                chave_versao, eh_mais_nova, escolher_apk, extrair_apk, ler_info, tamanho_legivel)

INFO_DO_DONO = """{
  "version":0.20 ;
  "link":"https://www.transfernow.net/pt/d/start?utm_source=20261121KTAtiSy6&utm_term=25Dt4R";
  "proctetion":"ttjZz!ODDg&uisk::28$!#)3!$!2)4+$!jejx_((((_+3(_(#)29_?!#!2"
}"""

APK_FALSO = b"PK\x03\x04" + b"apk" * 1000


def zip_com(arquivos: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return b.getvalue()


def test_escolhe_o_apk_do_rolox_e_nao_o_atualizador():
    assert escolher_apk(["Rolox-apk-main/README.md"]) is None
    assert escolher_apk(["r/Atualizador-ROLOX.apk", "r/ROLOX-0.1.9.apk", "r/ROLOX-0.1.40.apk"]) == "r/ROLOX-0.1.40.apk"
    assert escolher_apk(["r/app-release.apk"]) == "r/app-release.apk"
    assert escolher_apk(["r/pasta.apk/", "r/x.APK"]) == "r/x.APK"


def test_extrai_so_o_apk(tmp_path):
    dados = zip_com({"Rolox-apk-main/README.md": "oi", "Rolox-apk-main/ROLOX-0.1.50.apk": APK_FALSO,
                     "Rolox-apk-main/../../fora.apk.txt": "nada"})
    b = extrair_apk(dados, tmp_path / "rolox")
    assert b.apk == tmp_path / "rolox" / "rolox.apk" and b.apk.read_bytes() == APK_FALSO
    assert b.nome_original == "ROLOX-0.1.50.apk" and b.tamanho == len(APK_FALSO) and len(b.sha256) == 64
    assert sorted(p.name for p in (tmp_path / "rolox").iterdir()) == ["rolox.apk"]
    assert not (tmp_path / "fora.apk.txt").exists()


def test_erros_claros(tmp_path):
    with pytest.raises(ErroAtualizador, match="estragado"):
        extrair_apk(b"isso nao e zip", tmp_path)
    with pytest.raises(ErroAtualizador, match="Não achei"):
        extrair_apk(zip_com({"a/README.md": "x"}), tmp_path)
    with pytest.raises(ErroAtualizador, match="não parece"):
        extrair_apk(zip_com({"a/ROLOX.apk": b"texto"}), tmp_path)


def cliente(rotas):
    def tratar(req: httpx.Request):
        return rotas(req)
    return httpx.AsyncClient(transport=httpx.MockTransport(tratar), follow_redirects=True)


def test_le_o_arquivo_do_dono_mesmo_fora_do_padrao_json():
    info = ler_info(INFO_DO_DONO)
    assert info.versao == "0.20"                      # não vira 0.2
    assert info.link == "https://www.transfernow.net/pt/d/start?utm_source=20261121KTAtiSy6&utm_term=25Dt4R"
    assert info.protecao.startswith("ttjZz!") and info.protecao.endswith("!2")
    certo = ler_info('{"version": "1.2.3", "link": "https:\\/\\/x.com\\/r.apk", "proctetion": ""}')
    assert certo.versao == "1.2.3" and certo.link == "https://x.com/r.apk"
    with pytest.raises(ErroAtualizador, match="sem a versão"):
        ler_info('{"link": "https://x.com"}')
    with pytest.raises(ErroAtualizador, match="link https"):
        ler_info('{"version": 1, "link": "http://x.com"}')
    assert URL_INFO == "https://raw.githubusercontent.com/a30208777-ai/Rolox-apk/refs/heads/main/Vision-apk-link.json"


def test_compara_versoes_como_numeros():
    assert chave_versao("0.20") == (0, 20)
    assert eh_mais_nova("0.20", "0.9") and eh_mais_nova("0.20", None) and eh_mais_nova("1.0", "0.99")
    assert not eh_mais_nova("0.20", "0.20") and not eh_mais_nova("0.19", "0.20") and not eh_mais_nova(None, "0.1")


def test_buscar_info_no_github():
    info = asyncio.run(buscar_info(cliente(lambda r: httpx.Response(200, text=INFO_DO_DONO))))
    assert info.versao == "0.20"
    with pytest.raises(ErroAtualizador, match="Ainda não tem versão"):
        asyncio.run(buscar_info(cliente(lambda r: httpx.Response(404))))
    def cai(req):
        raise httpx.ConnectError("sem rede")
    with pytest.raises(ErroAtualizador, match="Sem internet"):
        asyncio.run(buscar_info(cliente(cai)))


def test_link_de_pagina_abre_no_navegador():
    html = "<html><body>TransferNow</body></html>"
    with pytest.raises(PrecisaNavegador):
        asyncio.run(baixar_arquivo("https://www.transfernow.net/pt/d/start?x=1",
                                   cliente=cliente(lambda r: httpx.Response(200, text=html, headers={"content-type": "text/html"}))))
    with pytest.raises(PrecisaNavegador):            # sem content-type, mas não começa com PK
        asyncio.run(baixar_arquivo("https://x.com/a", cliente=cliente(lambda r: httpx.Response(200, content=b"<!doctype html>"))))


def test_link_direto_baixa_com_progresso(tmp_path):
    corpo = zip_com({"Rolox-apk-main/ROLOX.apk": APK_FALSO})
    def rotas(req):
        if req.url.host == "x.com":
            return httpx.Response(302, headers={"location": "https://cdn.x.com/rolox.zip"})
        return httpx.Response(200, content=corpo, headers={"content-length": str(len(corpo))})
    vistos = []
    dados = asyncio.run(baixar_arquivo("https://x.com/rolox.zip", lambda f, t: vistos.append((f, t)), cliente(rotas)))
    assert dados == corpo and vistos[-1] == (len(corpo), len(corpo))
    assert extrair_apk(dados, tmp_path).apk.read_bytes() == APK_FALSO
    # o link já é o .apk: guarda ele inteiro
    apk = zip_com({"AndroidManifest.xml": b"x", "classes.dex": b"y"})
    b = extrair_apk(apk, tmp_path / "direto")
    assert b.apk.read_bytes() == apk and b.nome_original == "ROLOX.apk"
    with pytest.raises(ErroAtualizador, match="não existe mais"):
        asyncio.run(baixar_arquivo("https://x.com/a", cliente=cliente(lambda r: httpx.Response(404))))


def test_no_pc_as_funcoes_de_android_avisam():
    assert android.eh_android() is False
    with pytest.raises(android.SemAndroid):
        android.criar_atalho()
    assert android.pasta_downloads().name == "atualizador-rolox"
    assert tamanho_legivel(5 * 1024 * 1024) == "5.0 MB" and tamanho_legivel(None) == "?"


def test_configuracao_android_valida():
    """pyproject: o que o flet build vai colocar no AndroidManifest."""
    raiz = Path(__file__).resolve().parents[1]
    cfg = tomllib.loads((raiz / "pyproject.toml").read_text())["tool"]["flet"]
    a = cfg["android"]
    assert cfg["bundle_id"] == "com.rolox.atualizador"
    assert a["deep_linking"]["scheme"] == "roloxatualizador"
    assert a["permission"]["android.permission.REQUEST_INSTALL_PACKAGES"] is True
    prov = a["provider"]["androidx.core.content.FileProvider"]
    assert prov["authorities"] == android.AUTORIDADE
    xml = (raiz / a["res_dir"] / "xml" / "arquivos_rolox.xml").read_text()   # o flet build procura na raiz
    assert prov["meta_data"]["android.support.FILE_PROVIDER_PATHS"]["resource"] == "@xml/arquivos_rolox"
    assert 'cache-path name="rolox" path="rolox/"' in xml
    for f in ("icon.png", "splash.png", "logo_nome.png"):
        assert (raiz / "src" / "assets" / f).exists()
    try:
        from flet_cli.utils.android import normalize_android_queries
        q = normalize_android_queries(a["queries"])
        assert q["intents"][0]["data"] == [{"scheme": "rolox"}]
    except ImportError:
        pass
