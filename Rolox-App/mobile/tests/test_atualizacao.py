import asyncio
import tomllib
from pathlib import Path

import httpx

from rolox import atualizacao

ARQUIVO_DO_DONO = """{
  "version":0.20 ;
  "link":"https://www.transfernow.net/pt/d/start?utm_source=x";
  "proctetion":"ttjZz!ODDg&uisk::28$!#)3!$!2)4+$!jejx"
}"""


def test_versao_do_app_igual_ao_pyproject():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert atualizacao.VERSAO_APP == pyproject["project"]["version"]


def test_le_o_arquivo_do_dono():
    info = atualizacao.ler_info(ARQUIVO_DO_DONO)
    assert info.versao == "0.20" and info.link.startswith("https://www.transfernow.net/")
    assert info.protecao == "ttjZz!ODDg&uisk::28$!#)3!$!2)4+$!jejx"
    assert atualizacao.ler_info("{}") is None


def test_compara_versao_com_a_do_app():
    assert not atualizacao.tem_versao_nova("0.20", "0.24.0")
    assert atualizacao.tem_versao_nova("0.25", "0.24.0") and atualizacao.tem_versao_nova("1.0", "0.24.0")
    assert not atualizacao.tem_versao_nova("0.24", "0.24.0") and not atualizacao.tem_versao_nova(None, "0.24.0")


def test_sem_internet_segue_normal():
    def cai(req):
        raise httpx.ConnectError("sem rede")
    c = httpx.AsyncClient(transport=httpx.MockTransport(cai))
    assert asyncio.run(atualizacao.buscar_info(c)) is None
    ok = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=ARQUIVO_DO_DONO)))
    assert asyncio.run(atualizacao.buscar_info(ok)).versao == "0.20"


def test_marcas_ao_lado_do_nome():
    assert atualizacao.marca_app({"app": "oficial"}) == " ✅"
    assert atualizacao.marca_app({"app": "modificado"}) == " ❌"
    assert atualizacao.marca_app({"app": None}) == ""
    assert atualizacao.marca_app({"app_status": "oficial", "app_verificado_em": "2000-01-01T00:00:00+00:00"}) == ""
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc).isoformat()
    assert atualizacao.marca_app({"app_status": "oficial", "app_verificado_em": agora}) == " ✅"
