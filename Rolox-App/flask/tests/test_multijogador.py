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
    assert outros == [{"id": "u1", "n": "ana", "a": {"camisa": "#1e88e5"}, "p": [1.0, 2.0, 3.0], "r": 1.0, "m": True, "v": True, "pc": False, "dn": False, "em": None}]
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
    assert e == {"p": [0.0, 0.0, mj.LIMITE_COORD], "r": 0.0, "m": True, "v": True, "em": None}


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


# ------------------------------------------------ anfitrião, mundo compartilhado e Rede
A, B, C = ("aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002",
           "cccccccc-0000-0000-0000-000000000003")


def ps(u):
    return {"s": "s9", "u": u, "n": u[:4], "a": {}}


def test_primeiro_a_entrar_e_o_anfitriao_e_outro_assume(tmp_path):
    salas = mj.Salas(tmp_path)
    assert salas.trocar(ps(A), {}, agora=100)["anfitriao"] == A
    assert salas.trocar(ps(B), {}, agora=101)["anfitriao"] == A
    # A some (6 s sem atualizar): B vira anfitrião
    assert salas.trocar(ps(B), {}, agora=100 + mj.SUMIU_APOS + 2)["anfitriao"] == B


def test_so_o_anfitriao_muda_o_mundo_e_quem_chega_depois_recebe(tmp_path):
    salas = mj.Salas(tmp_path)
    salas.trocar(ps(A), {}, agora=100)
    porta = {"k": "w/2", "props": {"Transparency": 0.8, "CanCollide": False, "Position": [0, 3, -12]}}
    salas.trocar(ps(A), {"mundo": {"m": [porta, {"k": "n1-ab12c", "c": "Part", "p": "w", "props": {"Name": "Bala"}}],
                                    "d": ["w/5"]}}, agora=100.1)
    # B tenta trapacear: mexe no mundo sem ser anfitrião (ignorado)
    salas.trocar(ps(B), {"mundo": {"m": [{"k": "w/2", "props": {"Transparency": 0}}]}}, agora=100.2)
    r = salas.trocar(ps(B), {"mv": 0}, agora=100.3)
    porK = {it["k"]: it for it in r["mundo"]}
    assert porK["w/2"]["props"] == {"Transparency": 0.8, "CanCollide": False, "Position": [0.0, 3.0, -12.0]}
    assert porK["n1-ab12c"]["c"] == "Part" and porK["w/5"] == {"k": "w/5", "x": 1}
    # já atualizado: nada novo
    assert salas.trocar(ps(B), {"mv": r["mv"]}, agora=100.4)["mundo"] == []
    # o anfitrião não recebe o próprio mundo de volta
    assert salas.trocar(ps(A), {"mv": 0}, agora=100.5)["mundo"] == []


def test_mundo_rejeita_lixo(tmp_path):
    salas = mj.Salas(tmp_path)
    salas.trocar(ps(A), {"mundo": {"m": [
        {"k": "../../etc", "props": {}}, {"k": "w/1", "c": "Script", "props": {"Source": "rm -rf"}},
        {"k": "w/2", "props": {"Color": "red; x", "Transparency": "muito", "Position": [1, "a", 3], "Shape": "Pizza",
                               "Name": "x" * 500}}]}}, agora=1)
    r = salas.trocar(ps(B), {"mv": 0}, agora=2)
    porK = {it["k"]: it for it in r["mundo"]}
    assert "../../etc" not in porK
    assert "c" not in porK["w/1"] and porK["w/1"]["props"] == {}
    assert porK["w/2"]["props"] == {"Name": "x" * 60}


def test_rede_jogador_para_anfitriao_e_anfitriao_para_todos(tmp_path):
    salas = mj.Salas(tmp_path)
    salas.trocar(ps(A), {}, agora=1)
    salas.trocar(ps(B), {}, agora=1.1)
    salas.trocar(ps(C), {}, agora=1.2)
    # B pede ao servidor (anfitrião A)
    salas.trocar(ps(B), {"eventos": [{"para": "servidor", "nome": "abrirPorta", "dados": 7},
                                       {"para": "todos", "nome": "trapaca", "dados": 1},       # só o anfitrião pode
                                       {"para": "servidor", "nome": "<script>", "dados": 1},    # nome inválido
                                       {"para": "servidor", "nome": "x", "dados": {"obj": 1}}]}, agora=1.3)
    r = salas.trocar(ps(A), {}, agora=1.4)
    assert r["eventos"] == [{"de": B, "nome": "abrirPorta", "dados": 7.0, "para": "servidor"}]
    # A responde para todos (inclusive ele) e para C em particular
    salas.trocar(ps(A), {"eventos": [{"para": "todos", "nome": "portaAberta", "dados": True},
                                      {"para": C, "nome": "segredo", "dados": "só seu"}]}, agora=1.5)
    assert salas.trocar(ps(B), {}, agora=1.6)["eventos"] == [{"de": A, "nome": "portaAberta", "dados": True, "para": "jogadores"}]
    assert [e["nome"] for e in salas.trocar(ps(C), {}, agora=1.6)["eventos"]] == ["portaAberta", "segredo"]
    assert salas.trocar(ps(C), {}, agora=1.7)["eventos"] == []           # entregue uma vez só


def test_sala_vazia_recomeca_o_mundo(tmp_path):
    salas = mj.Salas(tmp_path)
    salas.trocar(ps(A), {"mundo": {"m": [{"k": "w/2", "props": {"Transparency": 1}}]}}, agora=1)
    r = salas.trocar(ps(B), {"mv": 0}, agora=100)        # A sumiu e a sala ficou vazia antes de B
    assert r["anfitriao"] == B and r["mundo"] == []


def test_gestos_so_os_da_lista():
    assert mj.limpar_estado({"em": "dancar"})["em"] == "dancar"
    assert mj.limpar_estado({"em": "<script>"})["em"] is None
    assert mj.limpar_estado({"em": ["acenar"]})["em"] is None
