"""Testes do NPC com IA (modelos simulados, sem internet).

Rodar:  cd IA && python -m pytest -q
"""

import pytest

from modelos import Roteador, carregar_modelos
from npc_ia import NPC, Personagem, filtrar_texto


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def roteador_falso(respostas, modelos=None, relogio=None, **kw):
    """Cada chamada consome a próxima resposta: str = sucesso, ('erro', motivo) = falha."""
    chamadas = []
    fila = list(respostas)

    def chamador(nome, url, chave, mensagens, timeout):
        chamadas.append({"modelo": nome, "mensagens": mensagens, "timeout": timeout})
        r = fila.pop(0)
        if isinstance(r, tuple):
            return None, r[1]
        return r, None

    rt = Roteador(modelos or [("m1", "u1", None), ("m2", "u2", "k")],
                  chamador=chamador, relogio=relogio or Relogio(), **kw)
    return rt, chamadas


def personagem(**kw):
    base = dict(nome="Dona Lúcia", papel="ferreira", personalidade="rabugenta",
                acoes_permitidas={"dar_item": "entregar item", "abrir_loja": "mostrar loja"},
                falas_reserva=["Volta depois!"])
    base.update(kw)
    return Personagem(**base)


# ---------------------------------------------------------------- filtro
def test_filtro_igual_ao_do_banco():
    assert filtrar_texto("hj eu achei um cão mais era a porra de uma sacola") == \
        "hj eu achei um cão mais era uma sacola"
    assert filtrar_texto("vsf seu fdp, bora jogar") == "seu, bora jogar"


# --------------------------------------------------------------- resposta
def test_resposta_com_emocao_e_acao_permitida():
    rt, _ = roteador_falso(["Toma essa espada, sô! [EMOCAO: feliz] [ACAO: dar_item espada_simples]"])
    r = NPC(personagem(), rt).falar("alice", "me dá uma espada?")
    assert r.texto == "Toma essa espada, sô!"
    assert r.emocao == "feliz"
    assert r.acoes == [("dar_item", "espada_simples")]
    assert r.modelo == "m1" and not r.reserva


def test_acao_fora_da_lista_e_ignorada():
    rt, _ = roteador_falso(["Pronto. [ACAO: apagar_servidor tudo] [ACAO: dar_moedas 9999] [EMOCAO: maluco]"])
    r = NPC(personagem(), rt).falar("alice", "oi")
    assert r.acoes == []
    assert r.emocao == "neutro"          # emoção inválida vira neutro
    assert r.texto == "Pronto."


def test_limpa_pensamento_markdown_nome_e_palavrao():
    rt, _ = roteador_falso(["<think>vou ser simpática</think>**Dona Lúcia:** Que porra de chuva, hein! [EMOCAO: bravo]"])
    r = NPC(personagem(), rt).falar("alice", "oi")
    assert r.texto == "Que chuva, hein!"
    assert r.emocao == "bravo"


def test_corta_resposta_longa_no_fim_da_frase():
    longa = "Essa é uma frase de exemplo bem comprida. " * 20
    rt, _ = roteador_falso([longa])
    r = NPC(personagem(max_caracteres=100), rt).falar("alice", "conta uma história")
    assert len(r.texto) <= 100 and r.texto.endswith(".")


# --------------------------------------------------------------- contexto
def test_prompt_tem_personagem_contexto_e_memoria():
    rt, chamadas = roteador_falso(["Oi de novo!"])
    npc = NPC(personagem(conhecimentos=["lobos na estrada do norte"]), rt)
    npc.lembrar("alice", "salvou o vilarejo dos lobos")
    npc.falar("alice", "oi", {"local": "forja", "hora": "noite"})
    sistema = chamadas[0]["mensagens"][0]["content"]
    for trecho in ["Dona Lúcia", "rabugenta", "lobos na estrada do norte", "local: forja",
                   "hora: noite", "salvou o vilarejo dos lobos", "Nunca saia do personagem",
                   "dar_item"]:
        assert trecho in sistema


def test_memoria_e_separada_por_jogador_e_guarda_a_conversa():
    rt, chamadas = roteador_falso(["Prazer, Alice.", "Quem é você?", "Lembro sim, Alice."])
    npc = NPC(personagem(), rt)
    npc.falar("alice", "meu nome é Alice")
    npc.falar("bob", "oi")
    npc.falar("alice", "lembra de mim?")
    msgs_bob = chamadas[1]["mensagens"]
    msgs_alice = chamadas[2]["mensagens"]
    assert all("Alice" not in m["content"] for m in msgs_bob[1:])
    assert {"role": "assistant", "content": "Prazer, Alice."} in msgs_alice


def test_memoria_tem_limite():
    rt, chamadas = roteador_falso([f"resposta {i}" for i in range(20)])
    npc = NPC(personagem(), rt)
    for i in range(20):
        npc.falar("alice", f"fala {i}")
    assert len(chamadas[-1]["mensagens"]) <= 1 + 12 + 1


# ----------------------------------------------------------- troca de modelo
def test_troca_de_modelo_e_pausa_quem_bateu_limite():
    relogio = Relogio()
    rt, chamadas = roteador_falso([("erro", "limite HTTP 429"), "Oi!", "De novo!"], relogio=relogio)
    npc = NPC(personagem(), rt)
    assert npc.falar("alice", "oi").modelo == "m2"
    assert npc.falar("alice", "oi").modelo == "m2"   # m1 continua pausado
    assert [c["modelo"] for c in chamadas] == ["m1", "m2", "m2"]
    relogio.t = 500                                   # passou a pausa
    assert [m[0] for m in rt.em_ordem()] == ["m1", "m2"]


def test_sem_modelo_usa_fala_de_reserva_e_nao_guarda_memoria():
    rt, chamadas = roteador_falso([("erro", "conexão"), ("erro", "erro HTTP 500")])
    npc = NPC(personagem(), rt)
    r = npc.falar("alice", "oi")
    assert r.texto == "Volta depois!" and r.reserva
    assert list(npc._memoria("alice").falas) == []


def test_resposta_vazia_depois_do_filtro_vira_reserva():
    rt, _ = roteador_falso(["[EMOCAO: feliz]"])
    assert NPC(personagem(), rt).falar("alice", "oi").reserva


def test_prazo_total_e_respeitado():
    relogio = Relogio()

    def lento(nome, url, chave, msgs, timeout):
        relogio.t += timeout                      # cada modelo gasta todo o tempo
        return None, "conexão: timeout"

    modelos = [(f"m{i}", "u", None) for i in range(10)]
    rt = Roteador(modelos, prazo=12, timeout_por_modelo=8, chamador=lento, relogio=relogio)
    assert rt.perguntar([]) == (None, None)
    assert relogio.t <= 12


def test_preferido_vai_primeiro():
    rt, chamadas = roteador_falso(["ok"])
    rt.preferido = "m2"
    rt.perguntar([])
    assert chamadas[0]["modelo"] == "m2"


def test_registro_e_chamado_e_erro_no_registro_nao_quebra():
    vistos = []

    def registrar(npc, jogador, fala, resposta):
        vistos.append((npc, jogador, fala, resposta.texto))
        raise RuntimeError("supabase fora do ar")

    rt, _ = roteador_falso(["Oi!"])
    NPC(personagem(), rt, ao_registrar=registrar).falar("alice", "oi")
    assert vistos == [("Dona Lúcia", "alice", "oi", "Oi!")]


# ----------------------------------------------------------------- modelos
def test_modelos_sem_chave_ficam_de_fora(monkeypatch):
    for v in ["CHAVE_AION", "CHAVE_COHERE", "CHAVE_GEMINI", "CHAVE_MISTRAL", "CHAVE_ZAI",
              "CHAVE_GONKA", "CHAVE_GROQ", "CHAVE_MODELSCOPE", "CHAVE_NVIDIA",
              "CHAVE_OPENROUTER", "CHAVE_SILICONFLOW"]:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("CHAVE_GROQ", "gsk_teste")
    ms = carregar_modelos()
    assert all(chave is None or chave == "gsk_teste" for _, _, chave in ms)
    assert not any("openrouter.ai" in url for _, url, _ in ms)
    assert ("openai/gpt-oss-120b", "https://api.groq.com/openai/v1/chat/completions", "gsk_teste") in ms


def test_provedor_fora_do_ar_pula_todos_os_modelos_dele():
    modelos = [("a1", "url_a", None), ("a2", "url_a", None), ("a3", "url_a", None), ("b1", "url_b", None)]
    rt, chamadas = roteador_falso([("erro", "provedor fora: ConnectionError"), "Oi!"], modelos=modelos)
    assert rt.perguntar([]) == ("b1", "Oi!")
    assert [c["modelo"] for c in chamadas] == ["a1", "b1"]
