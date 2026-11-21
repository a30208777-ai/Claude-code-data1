"""Testes do cliente da API (sem rede: usa um Supabase falso)."""

import asyncio
import json

import httpx
import pytest

from rolox.api import ErroRolox, RoloxAPI, Sessao


def rodar(coro):
    return asyncio.run(coro)


def api_com(handler) -> RoloxAPI:
    return RoloxAPI(url="https://falso.supabase.co", chave="sb_publishable_teste",
                    transport=httpx.MockTransport(handler))


def resposta(status, corpo):
    return httpx.Response(status, json=corpo)


# ------------------------------------------------------------------ login
def test_login_ok_guarda_sessao_e_manda_apikey():
    vistos = []

    def h(req: httpx.Request):
        vistos.append(req)
        assert req.url.path == "/functions/v1/login-protegido"
        assert json.loads(req.content) == {"username": "alice", "senha": "segredo123"}
        return resposta(200, {"access_token": "A", "refresh_token": "R", "user_id": "u1"})

    api = api_com(h)
    s = rodar(api.login("  Alice ", "segredo123"))
    assert s == Sessao("A", "R", "u1")
    assert vistos[0].headers["apikey"] == "sb_publishable_teste"
    assert "authorization" not in vistos[0].headers


def test_login_senha_errada_mostra_tentativas_restantes():
    api = api_com(lambda r: resposta(401, {"erro": "credenciais_invalidas", "tentativas_restantes": 1}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.login("alice", "errada"))
    assert e.value.codigo == "credenciais_invalidas"
    assert "Tentativas restantes: 1" in e.value.mensagem


def test_login_ip_bloqueado():
    api = api_com(lambda r: resposta(403, {"erro": "ip_bloqueado"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.login("alice", "x"))
    assert e.value.codigo == "ip_bloqueado"
    assert "bloqueado" in e.value.mensagem


def test_login_vazio_nem_chama_servidor():
    api = api_com(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ErroRolox) as e:
        rodar(api.login("", ""))
    assert e.value.codigo == "dados_invalidos"


def test_sem_internet_vira_erro_amigavel():
    def h(req):
        raise httpx.ConnectError("sem rede", request=req)

    with pytest.raises(ErroRolox) as e:
        rodar(api_com(h).login("alice", "x"))
    assert e.value.codigo == "sem_conexao"


# --------------------------------------------------------------- cadastro
@pytest.mark.parametrize("username", ["ab", "-alice", "alice-", "Al ice", "a" * 33, "ação"])
def test_cadastro_rejeita_username_invalido(username):
    api = api_com(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ErroRolox) as e:
        rodar(api.cadastrar(username, "12345678", False))
    assert e.value.codigo == "username_invalido"


def test_cadastro_sem_email_ja_entra():
    def h(req):
        assert req.url.path == "/functions/v1/cadastro"
        assert json.loads(req.content) == {"username": "alice-1", "senha": "12345678", "email": "",
                                           "aceitou_localizacao": True}
        return resposta(201, {"access_token": "A", "refresh_token": "R", "user_id": "u1"})

    api = api_com(h)
    assert rodar(api.cadastrar("Alice-1", "12345678", True)) == Sessao("A", "R", "u1")
    assert api.sessao.user_id == "u1"


def test_cadastro_email_opcional_valida_formato():
    api = api_com(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ErroRolox) as e:
        rodar(api.cadastrar("alice", "12345678", False, "nao-e-email"))
    assert e.value.codigo == "email_invalido"


def test_cadastro_username_duplicado():
    api = api_com(lambda r: resposta(409, {"erro": "username_em_uso"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.cadastrar("alice", "12345678", False))
    assert "já está em uso" in e.value.mensagem


# ----------------------------------------------------------------- sessão
def test_token_expirado_renova_e_repete():
    chamadas = []

    def h(req):
        chamadas.append((req.url.path, req.headers.get("authorization")))
        if req.url.path == "/auth/v1/token":
            assert req.url.params["grant_type"] == "refresh_token"
            return resposta(200, {"access_token": "NOVO", "refresh_token": "R2", "user": {"id": "u1"}})
        if req.headers["authorization"] == "Bearer VELHO":
            return resposta(401, {"code": "PGRST303"})
        return resposta(200, [{"id": "u1", "username": "alice"}])

    api = api_com(h)
    api.sessao = Sessao("VELHO", "R1", "u1")
    perfil = rodar(api.meu_perfil())
    assert perfil["username"] == "alice"
    assert api.sessao == Sessao("NOVO", "R2", "u1")
    assert [c[0] for c in chamadas] == ["/rest/v1/perfis", "/auth/v1/token", "/rest/v1/perfis"]


def test_refresh_invalido_encerra_sessao():
    api = api_com(lambda r: resposta(400, {"error_code": "refresh_token_not_found"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.renovar("ruim"))
    assert e.value.codigo == "sessao_expirada"
    assert api.sessao is None


def test_chamada_logada_sem_sessao():
    api = api_com(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ErroRolox) as e:
        rodar(api.alertas())
    assert e.value.codigo == "sessao_expirada"


# -------------------------------------------------------------- servidores
def logada(handler) -> RoloxAPI:
    api = api_com(handler)
    api.sessao = Sessao("T", "R", "u1")
    return api


def test_lista_servidores_conta_jogadores():
    def h(req):
        assert "users_dos_servidores(count)" in req.url.params["select"]
        return resposta(200, [
            {"server_uid": "s1", "gameid": "corrida", "capacidade": 10, "is_hack_server": False,
             "status": "aberto", "host_id": "u2", "users_dos_servidores": [{"count": 3}],
             "bots_dos_servidores": [{"count": 5}]},
        ])

    s = rodar(logada(h).servidores())
    assert (s[0]["humanos"], s[0]["ias"], s[0]["jogadores"]) == (3, 5, 8)
    assert "users_dos_servidores" not in s[0] and "bots_dos_servidores" not in s[0]


def test_entrar_fila():
    def h(req):
        assert req.url.path == "/rest/v1/rpc/entrar_servidor"
        assert json.loads(req.content) == {"p_server": "s1"}
        return resposta(200, {"resultado": "fila", "posicao": 2})

    assert rodar(logada(h).entrar("s1"))["posicao"] == 2


def test_entrar_bloqueado_por_hack_vira_erro():
    api = logada(lambda r: resposta(200, {"resultado": "use_servidor_hack"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.entrar("s1"))
    assert "servidor de hack" in e.value.mensagem


def test_criar_servidor_valida_capacidade():
    api = logada(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ValueError):
        rodar(api.criar_servidor("corrida", 0, False))


def test_criar_servidor_usa_meu_id_como_host():
    def h(req):
        corpo = json.loads(req.content)
        assert corpo == {"gameid": "corrida", "host_id": "u1", "capacidade": 8, "is_hack_server": True}
        assert req.headers["prefer"] == "return=representation"
        return resposta(201, [dict(corpo, server_uid="s9")])

    assert rodar(logada(h).criar_servidor("corrida", 8, True))["server_uid"] == "s9"


def test_onde_estou_na_fila_calcula_posicao():
    def h(req):
        p = req.url.path
        if p == "/rest/v1/users_dos_servidores":
            return resposta(200, [])
        if req.url.params.get("user_id") == "eq.u1":
            return resposta(200, [{"server_uid": "s1", "id": 7}])
        assert req.url.params["id"] == "lte.7"
        return resposta(200, [{"id": 3}, {"id": 7}])

    assert rodar(logada(h).onde_estou()) == {"servidor": None, "fila": "s1", "posicao": 2}


# ------------------------------------------------------------- perfil/chat
def test_email_do_perfil_normaliza_e_remove():
    enviados = []

    def h(req):
        enviados.append(json.loads(req.content))
        return resposta(200, [{"id": "u1"}])

    api = logada(h)
    rodar(api.atualizar_perfil(email=" Alice@Ex.com "))
    rodar(api.atualizar_perfil(email=""))
    assert enviados == [{"email": "alice@ex.com"}, {"email": None}]
    with pytest.raises(ErroRolox):
        rodar(api.atualizar_perfil(email="errado"))


def test_perfil_so_aceita_campos_editaveis():
    api = logada(lambda r: pytest.fail("não deveria chamar a rede"))
    with pytest.raises(ValueError):
        rodar(api.atualizar_perfil(is_admin=True))


def test_enviar_muito_rapido():
    api = logada(lambda r: resposta(200, {"resultado": "muito_rapido"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.enviar("s1", "oi"))
    assert e.value.codigo == "muito_rapido"


def test_mensagens_pede_so_as_novas():
    def h(req):
        assert req.url.params["id"] == "gt.42"
        assert req.url.params["select"] == "id,username,mensagem_filtrada,criado_em,bot_id"
        return resposta(200, [])

    assert rodar(logada(h).mensagens("s1", 42)) == []


def test_ver_senha_tentada():
    def h(req):
        assert req.url.path == "/functions/v1/ver-alerta"
        assert req.headers["authorization"] == "Bearer T"
        return resposta(200, {"senha_tentada": "123456"})

    assert rodar(logada(h).ver_senha_tentada(5)) == "123456"


def test_backend_nao_configurado_explica_o_erro():
    api = api_com(lambda r: resposta(404, {"code": "NOT_FOUND", "message": "Requested function was not found"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.login("admtest", "x"))
    assert "ainda não foi configurado" in e.value.mensagem


# ------------------------------------------------------ tickets, ADM, avatar
from rolox import avatar as av  # noqa: E402


def test_receber_tickets():
    def h(req):
        assert req.url.path == "/rest/v1/rpc/receber_tickets_diarios"
        return resposta(200, {"infinito": False, "ganhou": 10, "tickets": 15, "amanha": 20})

    assert rodar(logada(h).receber_tickets())["amanha"] == 20


def test_acoes_de_adm_chamam_as_rpcs_certas():
    vistos = []

    def h(req):
        vistos.append((req.url.path.rsplit("/", 1)[1], json.loads(req.content)))
        return resposta(200, {"tickets": 1})

    api = logada(h)
    rodar(api.adm_dar_tickets("u9", 10))
    rodar(api.adm_banir("u9", "spam"))
    rodar(api.adm_desbanir("u9"))
    rodar(api.adm_definir_adm("u9", True))
    rodar(api.adm_desbloquear_ip("1.2.3.4"))
    rodar(api.adm_encerrar_servidor("s1"))
    assert vistos == [("adm_dar_tickets", {"p_user": "u9", "p_qtd": 10}),
                      ("adm_banir", {"p_user": "u9", "p_motivo": "spam"}),
                      ("adm_desbanir", {"p_user": "u9"}),
                      ("adm_definir_adm", {"p_user": "u9", "p_adm": True}),
                      ("adm_desbloquear_ip", {"p_ip": "1.2.3.4"}),
                      ("adm_encerrar_servidor", {"p_server": "s1"})]


def test_erro_de_permissao_mostra_a_mensagem_do_servidor():
    api = logada(lambda r: resposta(403, {"code": "42501", "message": "apenas ADM"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.adm_painel())
    assert e.value.mensagem == "Apenas adm."


def test_avatar_normaliza_e_desenha():
    a = av.normalizar({"pele": "#8d5524", "cabelo": "moicano", "acessorio": "coroa",
                       "camisa": "javascript:x", "extra": "1"})
    assert a == dict(av.PADRAO, pele="#8d5524", cabelo="moicano", acessorio="coroa")
    pecas = av.pecas(a)
    assert all(0 <= x and x + w <= av.LARGURA and 0 <= y and y + h <= av.ALTURA for x, y, w, h, _, _ in pecas)
    assert any(cor == "#fbc02d" for *_, cor, _ in pecas)        # coroa
    assert len(av.pecas({"cabelo": "careca"})) < len(av.pecas({"cabelo": "topete"}))


def test_salvar_avatar_manda_so_valores_validos():
    enviados = []

    def h(req):
        enviados.append(json.loads(req.content))
        return resposta(200, [{"id": "u1"}])

    rodar(logada(h).atualizar_perfil(avatar={"pele": "<script>", "cabelo": "longo"}))
    assert enviados[0]["avatar"] == dict(av.PADRAO, cabelo="longo")


def test_sem_chat_do_adm_e_mensagem_para_o_jogador():
    vistos = []

    def h(req):
        vistos.append((req.url.path.rsplit("/", 1)[1], json.loads(req.content)))
        return resposta(200, {"username": "bob"})

    api = logada(h)
    rodar(api.adm_sem_chat("u9", 60, "spam"))
    rodar(api.adm_com_chat("u9"))
    rodar(api.adm_marcar_ip_registrado("1.2.3.4"))
    assert vistos == [("adm_sem_chat", {"p_user": "u9", "p_minutos": 60, "p_motivo": "spam"}),
                      ("adm_com_chat", {"p_user": "u9"}),
                      ("adm_marcar_ip_registrado", {"p_ip": "1.2.3.4"})]
    api = logada(lambda r: resposta(200, {"resultado": "sem_chat", "ate": "2026-11-20T15:30:00+00:00", "motivo": "spam"}))
    with pytest.raises(ErroRolox) as e:
        rodar(api.enviar("s1", "oi"))
    assert "sem chat até 15:30" in e.value.mensagem and "spam" in e.value.mensagem



def test_jogos_publicados_e_link_do_site():
    def h(req):
        assert req.url.path == "/rest/v1/mapas"
        assert req.url.params["caminho_aprovado"] == "not.is.null"
        assert req.url.params["order"].startswith("visitas.desc")
        return resposta(200, [{"id": "m1", "nome": "Obby", "descricao": "pule"}, {"id": None, "nome": "x"}, "lixo"])

    j = rodar(logada(h).jogos_publicados())
    assert j == [{"id": "m1", "nome": "Obby", "descricao": "pule"}]
    from rolox.api import RoloxAPI
    assert RoloxAPI.link_jogos().endswith("/jogos")
    assert RoloxAPI.link_jogos("m1").endswith("/jogos#mapa-m1")


def test_recordes_pega_o_melhor_de_cada_jogo():
    def h(req):
        assert req.url.path == "/rest/v1/placares" and req.url.params["mapa_id"] == "in.(m1,m2)"
        return resposta(200, [{"mapa_id": "m1", "username": "bia", "valor": 9, "estatistica": "Moedas"},
                              {"mapa_id": "m1", "username": "ana", "valor": 3, "estatistica": "Moedas"},
                              {"mapa_id": "m2", "username": "leo", "valor": 1, "estatistica": "Vitórias"}])
    r = rodar(logada(h).recordes(["m1", "m2", None]))
    assert r["m1"]["username"] == "bia" and r["m2"]["username"] == "leo"
    assert rodar(logada(h).recordes([])) == {}


def test_amigos_no_app():
    chamadas = []
    def h(req):
        chamadas.append((req.url.path, json.loads(req.content or b"{}")))
        if req.url.path.endswith("meus_amigos"):
            return resposta(200, [{"id": "u2", "username": "bob", "tipo": "amigo", "online": True}, {"id": None}, "x"])
        return resposta(200, {"status": "pendente"})
    api = logada(h)
    assert rodar(api.meus_amigos()) == [{"id": "u2", "username": "bob", "tipo": "amigo", "online": True}]
    assert rodar(api.pedir_amizade(" Bob ")) == {"status": "pendente"}
    assert chamadas[-1] == ("/rest/v1/rpc/pedir_amizade", {"p_username": "bob"})
    from rolox.api import RoloxAPI
    assert RoloxAPI.link_amigos().endswith("/amigos")


def test_link_entrar_no_site_ja_logado():
    def h(req):
        return resposta(200, [{"id": "u1", "username": "ana"}])
    api = logada(h)
    url = rodar(api.link_entrar_no_site("123e4567-e89b-12d3-a456-426614174000"))
    base, frag = url.split("#")
    assert base.endswith("/app/entrar") and "t=" in frag and "mapa=123e4567-e89b-12d3-a456-426614174000" in frag
    assert "?" not in base                      # token nunca vai na parte que chega ao servidor
    assert "ir=amigos" in rodar(api.link_entrar_no_site(None, "amigos"))
    assert "mapa=" not in rodar(api.link_entrar_no_site("../../x"))


def test_usar_chave_parceria():
    chamadas = []
    def h(req):
        chamadas.append(json.loads(req.content))
        return resposta(200, {"parceiro": True, "apelido": "Canal"})
    api = logada(h)
    assert rodar(api.usar_chave_parceria("  abc!(+arthurdevpromax.io ")) == {"parceiro": True, "apelido": "Canal"}
    assert chamadas[-1] == {"p_chave": "abc!(+arthurdevpromax.io"}
    import pytest
    with pytest.raises(ValueError):
        rodar(api.usar_chave_parceria("   "))


def test_definir_redes_so_manda_redes_conhecidas():
    chamadas = []
    def h(req):
        chamadas.append(json.loads(req.content))
        return resposta(200, {"redes": {}})
    rodar(logada(h).definir_redes({"youtube": " https://youtube.com/@a ", "orkut": "x"}))
    assert chamadas[-1] == {"p_redes": {"youtube": "https://youtube.com/@a"}}


def test_buscar_no_app():
    chamadas = []
    def h(req):
        chamadas.append((req.url.path, json.loads(req.content)))
        return resposta(200, [{"username": "exemp", "nivel": 0}] if "jogadores" in req.url.path else [])
    r = rodar(logada(h).buscar("  Exemp  "))
    assert r["jogadores"][0]["username"] == "exemp" and r["jogos"] == []
    assert chamadas[0][1]["p_termo"] == "exemp"
    assert rodar(logada(h).buscar("e")) == {"jogadores": [], "jogos": []}
    from rolox.api import RoloxAPI
    assert RoloxAPI.link_buscar("boné").endswith("/buscar?q=bon%C3%A9")


def test_verificar_app_manda_chave_e_versao():
    chamadas = []
    def h(req):
        chamadas.append((req.url.path, json.loads(req.content)))
        return resposta(200, {"status": "oficial"})
    api = logada(h)
    assert rodar(api.verificar_app("  ttjZz!chave ", "0.24.0")) == "oficial"
    assert chamadas[-1] == ("/rest/v1/rpc/verificar_app", {"p_chave": "ttjZz!chave", "p_versao": "0.24.0"})
