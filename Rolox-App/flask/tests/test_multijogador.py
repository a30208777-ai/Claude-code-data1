"""Testes do multijogador (sala em arquivo + passe assinado)."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import multijogador as mj  # noqa: E402


def passe(u, n="ana"):
    return {"s": "s9", "u": u, "n": n, "a": {"camisa": "#1e88e5"}}


def test_cada_um_ve_os_outros_e_nao_a_si(tmp_path):
    salas = mj.Salas(tmp_path)
    assert salas.atualizar(passe("u1", "ana"), {"p": [1, 2, 3], "r": 1, "m": True}, agora=100) == []
    outros = salas.atualizar(passe("u2", "bia"), {"p": [5, 0, 5]}, agora=100.1)
    assert outros == [{"id": "u1", "n": "ana", "a": {"camisa": "#1e88e5"}, "p": [1.0, 2.0, 3.0], "r": 1.0, "m": True, "v": True, "pc": False}]
    assert [j["id"] for j in salas.atualizar(passe("u1"), {"p": [1, 2, 4]}, agora=100.2)] == ["u2"]


def test_quem_some_sai_da_sala(tmp_path):
    salas = mj.Salas(tmp_path)
    salas.atualizar(passe("u1"), {"p": [0, 0, 0]}, agora=100)
    assert salas.atualizar(passe("u2"), {}, agora=100 + mj.SUMIU_APOS + 1) == []
    salas.atualizar(passe("u3"), {}, agora=200)
    salas.sair(passe("u3"))
    assert salas.atualizar(passe("u2"), {}, agora=200.1) == []


def test_estado_maluco_e_limpo():
    e = mj.limpar_estado({"p": ["<script>", float("nan"), 1e99, 7], "r": "x", "m": "sim", "extra": "lixo"})
    assert e == {"p": [0.0, 0.0, mj.LIMITE_COORD], "r": 0.0, "m": True, "v": True}


def test_passe_assinado(tmp_path):
    ps = mj.Passes("segredo")
    t = ps.criar("s9", "u1", "ana", {})
    assert ps.ler(t)["u"] == "u1"
    assert ps.ler(t[:-2] + "xx") is None
    assert mj.Passes("outro").ler(t) is None
    assert ps.ler(mj.Passes("segredo").s.dumps({"s": "../etc", "u": "u1"})) is None


def test_muitos_ao_mesmo_tempo_nao_corrompe(tmp_path):
    salas = mj.Salas(tmp_path)
    def jogar(i):
        for k in range(20):
            salas.atualizar(passe(f"u{i}"), {"p": [i, k, 0]}, agora=1000 + k * 0.01)
    ts = [threading.Thread(target=jogar, args=(i,)) for i in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(salas.atualizar(passe("x"), {}, agora=1000.3)) == 8
