import asyncio
import io
import tomllib
import zipfile
from pathlib import Path

import httpx
import pytest

from atualizador import android
from atualizador.baixar import (URL_ZIP, URL_VERSAO, ErroAtualizador, baixar_zip, escolher_apk, extrair_apk,
                                tamanho_legivel, versao_online)

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


def test_baixa_com_progresso_e_segue_redirecionamento():
    corpo = zip_com({"Rolox-apk-main/ROLOX.apk": APK_FALSO})
    def rotas(req):
        if str(req.url) == URL_ZIP:
            return httpx.Response(302, headers={"location": "https://codeload.github.com/x.zip"})
        return httpx.Response(200, content=corpo, headers={"content-length": str(len(corpo))})
    vistos = []
    dados = asyncio.run(baixar_zip(lambda f, t: vistos.append((f, t)), cliente(rotas)))
    assert dados == corpo and vistos[-1] == (len(corpo), len(corpo))


def test_baixar_sem_versao_publicada_ou_sem_internet():
    with pytest.raises(ErroAtualizador, match="Ainda não tem versão"):
        asyncio.run(baixar_zip(cliente=cliente(lambda r: httpx.Response(404))))
    def cai(req):
        raise httpx.ConnectError("sem rede")
    with pytest.raises(ErroAtualizador, match="Sem internet"):
        asyncio.run(baixar_zip(cliente=cliente(cai)))


def test_versao_online():
    sha = "a" * 40
    assert asyncio.run(versao_online(cliente(lambda r: httpx.Response(200, text=sha + "\n")))) == sha
    assert asyncio.run(versao_online(cliente(lambda r: httpx.Response(404)))) is None
    assert asyncio.run(versao_online(cliente(lambda r: httpx.Response(200, text="<html>")))) is None
    assert URL_VERSAO.endswith("/repos/a30208777-ai/Rolox-apk/commits/main")
    assert URL_ZIP == "https://github.com/a30208777-ai/Rolox-apk/archive/refs/heads/main.zip"


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
