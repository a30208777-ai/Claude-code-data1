import docs_ia
import ia_studio


def nomes(texto, antes=()):
    msgs = [{"role": "user", "content": t} for t in antes] + [{"role": "user", "content": texto}]
    return [d.nome for d in docs_ia.escolher(msgs)]


def test_escolhe_pelo_pedido_sem_acento_e_por_comeco_de_palavra():
    assert "porta" in nomes("Crie uma PORTA que abre")
    assert "moedas_placar" in nomes("quero moedinhas... não, MOEDAS e um placar")
    assert "obby" in nomes("faz um obby com lava")
    assert "sons_midia" in nomes("toca uma música")
    assert "erros_comuns" in nomes("deu erro attempt to index nil")
    assert nomes("oi") == ["00_regras_de_ouro"]


def test_continua_usa_os_pedidos_anteriores_e_respeita_o_limite():
    assert "obby" in nomes("continua", antes=["faz um obby"])
    tudo = "porta moeda obby casa som video rede tempo dano internet emblema erro python mover tela"
    escolhidos = docs_ia.escolher([{"role": "user", "content": tudo}])
    assert len(escolhidos) <= docs_ia.MAX_DOCS + 1
    assert sum(len(d.texto) for d in escolhidos) <= docs_ia.MAX_CARACTERES


def test_documentos_vao_junto_para_a_ia():
    enviado = {}

    class R:
        status_code = 200
        def json(self): return {"choices": [{"message": {"content": "ok"}}]}

    class Http:
        @staticmethod
        def post(url, headers, json, timeout):
            enviado.update(json)
            return R()

    modelo, texto = ia_studio.perguntar([{"role": "user", "content": "cria uma porta"}], http=Http)
    sistema = enviado["messages"][0]["content"]
    assert texto == "ok" and "DOCUMENTOS DO ROLOX" in sistema and "Receita: porta que abre" in sistema
    assert "Regras de ouro" in sistema and "palavras:" not in sistema
