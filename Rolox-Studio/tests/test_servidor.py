"""Testes do servidor do Vista Studio.  Rodar: python -m pytest -q"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from servidor import CentralPCtoCelular, criar_app, eh_local, via_da_conexao  # noqa: E402

PROJETO = {"formato": "rolox-studio", "versao": 1, "nome": "x", "servicos": {"Workspace": []}, "assets": {}}


@pytest.fixture
def cliente(tmp_path):
    app = criar_app(tmp_path)
    app.testing = True
    return app.test_client()


def de_fora(**kw):
    return {"environ_overrides": {"REMOTE_ADDR": "192.168.44.20"}, **kw}


# ------------------------------------------------------------- páginas
def test_paginas_abrem_no_proprio_aparelho(cliente):
    assert cliente.get("/").status_code == 200
    assert b'data-modo="leve"' in cliente.get("/studio/leve").data
    assert b'data-modo="pesado"' in cliente.get("/studio/pc").data
    assert cliente.get("/studio/outro").status_code == 404


def test_studio_e_projetos_bloqueados_para_outros_aparelhos(cliente):
    assert cliente.get("/studio/pc", **de_fora()).status_code == 403
    assert cliente.get("/api/projetos", **de_fora()).status_code == 403
    assert cliente.put("/api/projetos/a", json=PROJETO, **de_fora()).status_code == 403


def test_controle_e_pagina_do_link_abrem_de_qualquer_aparelho(cliente):
    assert cliente.get("/controle", **de_fora()).status_code == 200
    r = cliente.get("/aprender/python-no-celular", **de_fora())
    assert r.status_code == 200 and "Python no celular".encode() in r.data


# ------------------------------------------------------------ projetos
def test_salvar_listar_abrir(cliente):
    assert cliente.put("/api/projetos/meu-jogo", json=PROJETO).get_json() == {"ok": True, "nome": "meu-jogo"}
    lista = cliente.get("/api/projetos").get_json()
    assert [p["nome"] for p in lista] == ["meu-jogo"]
    assert cliente.get("/api/projetos/meu-jogo").get_json()["formato"] == "rolox-studio"


@pytest.mark.parametrize("nome", ["../etc", "a b", "x" * 41, "ação"])
def test_nome_invalido(cliente, nome):
    assert cliente.put(f"/api/projetos/{nome}", json=PROJETO).status_code in (400, 404)


def test_recusa_arquivo_que_nao_e_projeto(cliente):
    assert cliente.put("/api/projetos/a", json={"formato": "outro"}).status_code == 400
    assert cliente.get("/api/projetos/nao-existe").status_code == 404


# ------------------------------------------------------- PCtoCelular
class WsFalso:
    def __init__(self):
        self.recebidas = []

    def send(self, texto):
        self.recebidas.append(json.loads(texto))


def test_endereco_local_e_via():
    assert eh_local("127.0.0.1") and eh_local("::1") and not eh_local("192.168.0.5")
    assert via_da_conexao("127.0.0.1") == "cabo"           # adb reverse
    assert via_da_conexao("192.168.42.129") == "cabo"      # ancoragem USB
    assert via_da_conexao("192.168.44.5") == "bluetooth"   # ancoragem Bluetooth


def test_celular_precisa_do_studio_aberto_e_do_codigo():
    c = CentralPCtoCelular()
    _, erro = c.entrar(WsFalso(), "0000", "cabo", "Bia")
    assert "não está aberto" in erro
    host = WsFalso()
    codigo = c.novo_host(host)
    assert len(codigo) == 4 and codigo.isdigit()
    errado = "1234" if codigo != "1234" else "4321"
    _, erro = c.entrar(WsFalso(), errado, "cabo", "Bia")
    assert "Código errado" in erro
    ident, erro = c.entrar(WsFalso(), codigo, "cabo", "Bia<script>")
    assert erro is None
    assert host.recebidas[-1] == {"tipo": "entrou", "id": ident, "nome": "Biascript", "via": "cabo"}


def test_limites_5_bluetooth_e_2_cabo():
    c = CentralPCtoCelular()
    codigo = c.novo_host(WsFalso())
    for i in range(2):
        assert c.entrar(WsFalso(), codigo, "cabo", f"c{i}")[1] is None
    assert "no máximo 2" in c.entrar(WsFalso(), codigo, "cabo", "c3")[1]
    for i in range(5):
        assert c.entrar(WsFalso(), codigo, "bluetooth", f"b{i}")[1] is None
    assert "no máximo 5" in c.entrar(WsFalso(), codigo, "bluetooth", "b6")[1]


def test_dados_sao_limpos_e_so_vao_para_o_pc():
    c = CentralPCtoCelular()
    host = WsFalso()
    codigo = c.novo_host(host)
    ident, _ = c.entrar(WsFalso(), codigo, "bluetooth", "Bia")
    c.dados(ident, {"x": 9, "z": "nan", "pular": 1, "modo": "sensor", "url": "http://evil",
                    "sensor": {"alpha": 90, "beta": -20, "gamma": 5, "altura": 0.3, "gps": "x"}})
    m = host.recebidas[-1]
    assert m == {"tipo": "dados", "id": ident, "x": 1.0, "z": 0.0, "pular": True, "modo": "sensor",
                 "sensor": {"alpha": 90.0, "beta": -20.0, "gamma": 5.0, "altura": 0.3}}
    c.sair(ident)
    assert host.recebidas[-1] == {"tipo": "saiu", "id": ident}
    c.dados(ident, {"x": 1})                    # depois de sair: ignorado
    assert host.recebidas[-1]["tipo"] == "saiu"


def test_pc_fechou_avisa_celulares():
    c = CentralPCtoCelular()
    host, cel = WsFalso(), WsFalso()
    codigo = c.novo_host(host)
    c.entrar(cel, codigo, "cabo", "Bia")
    c.host_saiu(host)
    assert cel.recebidas[-1]["tipo"] == "erro"
    assert c.entrar(WsFalso(), codigo, "cabo", "Bia")[1].startswith("O Studio do PC não está aberto")


def test_site_do_rolox_pode_ler_projetos(cliente):
    r = cliente.get("/api/projetos", headers={"Origin": "https://rolox-gj2i.onrender.com"})
    assert r.headers["Access-Control-Allow-Origin"] == "https://rolox-gj2i.onrender.com"
    pre = cliente.options("/api/projetos", headers={"Origin": "https://rolox-gj2i.onrender.com",
                                                    "Access-Control-Request-Private-Network": "true"})
    assert pre.headers["Access-Control-Allow-Private-Network"] == "true"


def test_outros_sites_nao_leem_projetos(cliente):
    r = cliente.get("/api/projetos", headers={"Origin": "https://site-malvado.com"})
    assert "Access-Control-Allow-Origin" not in r.headers
    r = cliente.get("/", headers={"Origin": "https://rolox-gj2i.onrender.com"})
    assert "Access-Control-Allow-Origin" not in r.headers
