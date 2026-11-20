"""Testes do Rolox Flask com um Supabase falso em memória (sem internet).

Rodar:  cd Rolox-App/flask && python -m pytest -q
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import criar_app  # noqa: E402
from rolox_api import RoloxAPI  # noqa: E402


class Resp:
    def __init__(self, status, corpo=None):
        self.status_code = status
        self._corpo = corpo
        self.content = b"" if corpo is None else json.dumps(corpo).encode()

    def json(self):
        if self._corpo is None:
            raise ValueError("vazio")
        return self._corpo


class SupabaseFalso:
    """Imita só o que o app usa do Supabase (REST, Auth e Edge Functions)."""

    def __init__(self):
        self.chamadas = []
        self.token_valido = "T1"
        self.perfil = {"id": "u1", "username": "alice", "email": None, "idioma": "pt-BR",
                       "jogo_mod": None, "aceitou_localizacao": True, "banido": False,
                       "is_adm": False, "tickets": 0, "tickets_ultimo_ganho": 0, "avatar": {}}
        self.presente = {"infinito": False, "ganhou": 5, "tickets": 5, "amanha": 10}
        self.adm_chamadas = []
        self.jogos = [{"gameid": "corrida", "nome": "Corrida Turbo"}]
        self.servidores = [
            {"server_uid": "s1", "gameid": "corrida", "host_id": "u2", "capacidade": 10,
             "is_hack_server": False, "status": "aberto"},
            {"server_uid": "s3", "gameid": "corrida", "host_id": "u4", "capacidade": 20,
             "is_hack_server": True, "status": "aberto"},
        ]
        self.membros = {"s1": ["u2", "u3"], "s3": ["u4"]}
        self.fila = []
        self.chat = [{"id": 1, "username": "bob", "mensagem_filtrada": "bora!",
                      "criado_em": "2026-11-16T00:10:00Z"}]
        self.alertas = [{"id": 9, "ip": "177.20.5.3", "ip_foi_banido": True, "lido": False,
                         "criado_em": "2026-11-15T22:40:00Z"}]
        self.falhas_login = 0
        self.cadastros = []
        self.fora_do_ar = False
        self.projetos = {}
        self.arquivos = {}
        self.mapas = {}
        self.dono = False
        self.curtidas = set()
        self.placares = {}
        self.amigos = []
        self.amizade_chamadas = []
        self.visitas = set()

    def onde(self):
        return next((s for s, m in self.membros.items() if "u1" in m), None)

    def request(self, metodo, url, json=None, params=None, headers=None, timeout=None, data=None):
        import requests
        if self.fora_do_ar:
            raise requests.ConnectionError("sem rede")
        p = urlsplit(url).path
        q = dict(params or {})
        self.chamadas.append((metodo, p, q, json, headers))
        auth = (headers or {}).get("Authorization", "")
        publicas = {"/functions/v1/login-protegido", "/functions/v1/cadastro", "/auth/v1/token"}
        if p not in publicas and p != "/rest/v1/jogos" and auth != f"Bearer {self.token_valido}":
            return Resp(401, {"code": "PGRST303"})

        if p == "/functions/v1/login-protegido":
            if json["senha"] == "certa":
                return Resp(200, {"access_token": self.token_valido, "refresh_token": "R1", "user_id": "u1"})
            self.falhas_login += 1
            if self.falhas_login >= 3:
                return Resp(403, {"erro": "ip_bloqueado"})
            return Resp(401, {"erro": "credenciais_invalidas", "tentativas_restantes": 3 - self.falhas_login})
        if p == "/functions/v1/cadastro":
            self.cadastros.append(json)
            if json["username"] == "bob":
                return Resp(409, {"erro": "username_em_uso"})
            return Resp(201, {"access_token": self.token_valido, "refresh_token": "R1", "user_id": "u1"})
        if p == "/auth/v1/token":
            if json["refresh_token"] == "R1":
                self.token_valido = "T2"
                return Resp(200, {"access_token": "T2", "refresh_token": "R2", "user": {"id": "u1"}})
            return Resp(400, {"error_code": "refresh_token_not_found"})
        if p == "/auth/v1/logout":
            return Resp(204)
        if p == "/auth/v1/user":
            return Resp(200, {"id": "u1"})
        if p == "/rest/v1/perfis":
            if metodo == "PATCH":
                self.perfil.update(json)
            return Resp(200, [self.perfil])
        if p == "/rest/v1/projetos_studio":
            if metodo == "POST":
                self.projetos[json["nome"]] = json
                return Resp(201)
            if "nome" in q:
                pj = self.projetos.get(q["nome"].removeprefix("eq."))
                return Resp(200, [{"dados": pj["dados"]}] if pj else [])
            return Resp(200, [{"nome": n, "tamanho": x["tamanho"]} for n, x in self.projetos.items()])
        if p.startswith("/storage/v1/object/"):
            resto = p.removeprefix("/storage/v1/object/")
            if metodo == "POST":
                assert resto.startswith("mapas/u1/"), "só grava na própria pasta"
                self.arquivos[resto.removeprefix("mapas/")] = data
                return Resp(200, {"Key": resto})
            chave = resto.removeprefix("authenticated/mapas/")
            if chave not in self.arquivos:
                return Resp(400, {"statusCode": "404", "error": "not_found"})
            r = Resp(200)
            r.content = self.arquivos[chave]
            return r
        if p == "/rest/v1/rpc/curtir_mapa":
            m = self.mapas[json["p_id"]]
            if json["p_curtir"] and m["id"] not in self.curtidas:
                self.curtidas.add(m["id"]); m["curtidas"] = m.get("curtidas", 0) + 1
            elif not json["p_curtir"] and m["id"] in self.curtidas:
                self.curtidas.discard(m["id"]); m["curtidas"] -= 1
            return Resp(200, {"curtidas": m["curtidas"], "curti": json["p_curtir"]})
        if p == "/rest/v1/rpc/registrar_placar":
            if json["p_id"] not in self.mapas or not self.mapas[json["p_id"]]["caminho_aprovado"]:
                return Resp(400, {"code": "P0001", "message": "jogo não encontrado"})
            k = (json["p_id"], "u1")
            antes = self.placares.get(k, {}).get("valor", -1)
            self.placares[k] = {"user_id": "u1", "username": "alice", "estatistica": json["p_estatistica"],
                                "valor": max(antes, json["p_valor"]), "atualizado_em": "x"}
            return Resp(200, {"recorde": self.placares[k]["valor"]})
        if p == "/rest/v1/placares":
            mid = q["mapa_id"].removeprefix("eq.")
            linhas = [v for (m, _), v in self.placares.items() if m == mid] + \
                     [{"user_id": "u7", "username": "bob", "estatistica": "Moedas", "valor": 5, "atualizado_em": "y"}]
            return Resp(200, sorted(linhas, key=lambda x: -x["valor"]))
        if p == "/rest/v1/rpc/meus_amigos":
            return Resp(200, self.amigos)
        if p in ("/rest/v1/rpc/pedir_amizade", "/rest/v1/rpc/responder_amizade", "/rest/v1/rpc/desfazer_amizade"):
            self.amizade_chamadas.append((p.rsplit("/", 1)[1], json))
            if p.endswith("pedir_amizade") and json["p_username"] == "fantasma":
                return Resp(400, {"code": "P0001", "message": "jogador não encontrado"})
            return Resp(200, {"status": "pendente"} if p.endswith("pedir_amizade") else None)
        if p == "/rest/v1/rpc/visitar_mapa":
            if json["p_id"] not in self.visitas:
                self.visitas.add(json["p_id"])
                self.mapas[json["p_id"]]["visitas"] = self.mapas[json["p_id"]].get("visitas", 0) + 1
            return Resp(204)
        if p == "/rest/v1/mapas_curtidas":
            return Resp(200, [{"mapa_id": i} for i in self.curtidas])
        if p == "/rest/v1/rpc/eh_dono":
            return Resp(200, self.dono)
        if p == "/rest/v1/rpc/enviar_mapa":
            assert json["p_caminho"] in self.arquivos
            m = self.mapas.setdefault(json["p_id"], {"id": json["p_id"], "autor_id": "u1", "caminho_aprovado": None,
                                                      "gameid": None, "motivo": None, "aprovado_em": None})
            m.update(nome=json["p_nome"], descricao=json["p_descricao"], caminho_enviado=json["p_caminho"],
                     status="em_analise", enviado_em="2026-11-20T05:00:00Z")
            return Resp(200, {"id": json["p_id"], "status": "em_analise"})
        if p.startswith("/rest/v1/rpc/dono_"):
            if not self.dono:
                return Resp(403, {"code": "42501", "message": "apenas o dono"})
            m = self.mapas[json["p_id"]]
            if p.endswith("aprovar_mapa"):
                m.update(status="aprovado", caminho_aprovado=m["caminho_enviado"], gameid="mapa-" + m["id"][:8],
                         aprovado_em="2026-11-20T06:00:00Z")
                self.jogos.append({"gameid": m["gameid"], "nome": m["nome"]})
            else:
                m.update(status="recusado", motivo=json["p_motivo"])
            return Resp(200, {"id": m["id"], "status": m["status"]})
        if p == "/rest/v1/mapas":
            lista = list(self.mapas.values())
            if "id" in q:
                lista = [m for m in lista if m["id"] == q["id"].removeprefix("eq.")]
            if q.get("caminho_aprovado") == "not.is.null":
                lista = [m for m in lista if m["caminho_aprovado"]]
            if "status" in q:
                lista = [m for m in lista if m["status"] == q["status"].removeprefix("eq.")]
            if "gameid" in q:
                lista = [m for m in lista if m.get("gameid") == q["gameid"].removeprefix("eq.")]
            if "autor_id" in q:
                lista = [m for m in lista if m["autor_id"] == q["autor_id"].removeprefix("eq.")]
            if q.get("order", "").startswith("visitas.desc"):
                lista.sort(key=lambda m: (-m.get("visitas", 0), -m.get("curtidas", 0)))
            return Resp(200, [dict(m) for m in lista])
        if p == "/rest/v1/jogos":
            return Resp(200, self.jogos)
        if p == "/rest/v1/servidores_ativos":
            if metodo == "GET":
                return Resp(200, [dict(s, users_dos_servidores=[{"count": len(self.membros.get(s["server_uid"], []))}],
                                       bots_dos_servidores=[{"count": s["capacidade"] // 2}])
                                  for s in self.servidores])
            if metodo == "PATCH":
                return Resp(204)
            novo = dict(json, server_uid="s9", status="aberto")
            self.servidores.append(novo)
            self.membros["s9"] = []
            return Resp(201, [novo])
        if p == "/rest/v1/users_dos_servidores":
            s = self.onde()
            return Resp(200, [{"server_uid": s}] if s else [])
        if p == "/rest/v1/espera":
            if q.get("user_id") == "eq.u1":
                return Resp(200, [{"server_uid": f, "id": 5} for f in self.fila])
            return Resp(200, [{"id": 4}, {"id": 5}])
        if p == "/rest/v1/rpc/entrar_servidor":
            uid = json["p_server"]
            srv = next((s for s in self.servidores if s["server_uid"] == uid), None)
            if srv["is_hack_server"] and self.perfil["jogo_mod"] != srv["gameid"]:
                return Resp(200, {"resultado": "servidor_so_para_hack"})
            if len(self.membros[uid]) >= srv["capacidade"]:
                self.fila.append(uid)
                return Resp(200, {"resultado": "fila", "posicao": 2})
            for m in self.membros.values():
                if "u1" in m:
                    m.remove("u1")
            self.membros[uid].append("u1")
            return Resp(200, {"resultado": "entrou"})
        if p == "/rest/v1/rpc/sair_servidor":
            self.membros[json["p_server"]].remove("u1")
            return Resp(200, {"resultado": "saiu"})
        if p == "/rest/v1/rpc/atualizar_local":
            return Resp(204)
        if p == "/rest/v1/rpc/enviar_mensagem":
            texto = json["p_texto"].strip()
            if not texto:
                return Resp(200, {"resultado": "tamanho_invalido"})
            self.chat.append({"id": len(self.chat) + 1, "username": "alice",
                              "mensagem_filtrada": re.sub(r"porra de ", "", texto),
                              "criado_em": "2026-11-16T00:12:00Z"})
            return Resp(200, {"resultado": "enviada"})
        if p == "/rest/v1/servidores_logados":
            depois = int(q["id"].split(".")[1])
            return Resp(200, [m for m in self.chat if m["id"] > depois])
        if p == "/rest/v1/rpc/receber_tickets_diarios":
            r = dict(self.presente)
            if r.get("ganhou"):
                self.perfil["tickets"] += r["ganhou"]
                self.presente = dict(r, ganhou=0)
            return Resp(200, r)
        if p.startswith("/rest/v1/rpc/adm_"):
            if not self.perfil["is_adm"]:
                return Resp(403, {"code": "42501", "message": "apenas ADM"})
            self.adm_chamadas.append((p.rsplit("/", 1)[1], json))
            if p.endswith("adm_painel"):
                return Resp(200, {"totais": {"usuarios": 2, "servidores": 1, "ips_bloqueados": 1, "alertas_hoje": 0},
                                  "usuarios": [{"id": "u1", "username": "alice", "tickets": 0, "is_adm": True, "banido": False},
                                               {"id": "u9", "username": "bob", "tickets": 7, "is_adm": False, "banido": False}],
                                  "ips_bloqueados": [{"ip": "1.2.3.4", "conta_alvo": "alice", "motivo": "x",
                                                      "bloqueado_em": "2026-11-18T00:00:00Z"}],
                                  "servidores": [{"server_uid": "s1", "gameid": "corrida", "capacidade": 10,
                                                  "is_hack_server": False, "humanos": 2, "ias": 5}]})
            return Resp(200, {"tickets": 17} if p.endswith("adm_dar_tickets") else None)
        if p == "/rest/v1/alertas_seguranca":
            return Resp(200, self.alertas)
        if p == "/functions/v1/ver-alerta":
            self.alertas[0]["lido"] = True
            return Resp(200, {"senha_tentada": "alice2024"})
        return Resp(404, {"erro": "rota_falsa " + p})


@pytest.fixture
def sb():
    return SupabaseFalso()


@pytest.fixture
def cliente(sb):
    app = criar_app(lambda s: RoloxAPI(s, url="https://falso", chave="k", http=sb), segredo="teste")
    app.testing = True
    return app.test_client()


def csrf(cliente):
    cliente.get("/login")
    with cliente.session_transaction() as s:
        return s["csrf"]


def entrar(cliente, senha="certa"):
    return cliente.post("/login", data={"usuario": "Alice", "senha": senha, "csrf": csrf(cliente)})


def html(r):
    return r.get_data(as_text=True)


# ------------------------------------------------------------------ login
def test_sem_login_vai_para_tela_de_login(cliente):
    r = cliente.get("/inicio")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")


def test_login_ok_e_inicio_mostra_alerta(cliente, sb):
    r = entrar(cliente)
    assert r.status_code == 302 and r.headers["Location"].endswith("/inicio")
    pagina = html(cliente.get("/inicio"))
    assert "Olá, alice!" in pagina
    assert "Alguém tentou entrar na sua conta" in pagina and "177.20.5.3" in pagina and "IP banido" in pagina
    assert sb.chamadas[0][3] == {"username": "alice", "senha": "certa"}


def test_senha_errada_mostra_tentativas_e_depois_bloqueio(cliente):
    r = entrar(cliente, "errada")
    assert r.status_code == 401 and "Tentativas restantes: 2" in html(r)
    entrar(cliente, "errada")
    r = entrar(cliente, "errada")
    assert "bloqueado após 3 senhas erradas" in html(r)


def test_post_sem_csrf_e_recusado(cliente):
    r = cliente.post("/login", data={"usuario": "alice", "senha": "certa"})
    assert r.status_code == 400


def test_token_expirado_renova_sozinho(cliente, sb):
    entrar(cliente)
    sb.token_valido = "EXPIRADO"           # o access token "T1" deixou de valer
    with cliente.session_transaction() as s:
        s["sb"]["refresh_token"] = "R1"
    r = cliente.get("/inicio")
    assert r.status_code == 200
    with cliente.session_transaction() as s:
        assert s["sb"]["access_token"] == "T2"


def test_refresh_invalido_volta_para_login(cliente, sb):
    entrar(cliente)
    sb.token_valido = "EXPIRADO"
    with cliente.session_transaction() as s:
        s["sb"]["refresh_token"] = "RUIM"
    r = cliente.get("/inicio")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    with cliente.session_transaction() as s:
        assert "sb" not in s


def test_sem_internet_mostra_erro_sem_loop(cliente, sb):
    entrar(cliente)
    sb.fora_do_ar = True
    r = cliente.get("/inicio")
    assert r.status_code == 503 and "Sem conexão" in html(r)


def test_sair_da_conta(cliente):
    entrar(cliente)
    token = csrf(cliente)
    cliente.post("/sair-da-conta", data={"csrf": token})
    assert cliente.get("/inicio").status_code == 302


# --------------------------------------------------------------- cadastro
def test_cadastro_valida_e_mostra_username_em_uso(cliente):
    token = csrf(cliente)
    r = cliente.post("/cadastro", data={"usuario": "-x", "senha": "12345678", "csrf": token})
    assert r.status_code == 400 and "O usuário deve ter" in html(r)
    r = cliente.post("/cadastro", data={"usuario": "bob", "senha": "12345678", "csrf": token})
    assert "já está em uso" in html(r)


def test_cadastro_sem_email_ja_entra(cliente, sb):
    r = cliente.post("/cadastro", data={"usuario": "Carol", "senha": "12345678", "localizacao": "on",
                                        "csrf": csrf(cliente)})
    assert r.status_code == 302 and r.headers["Location"].endswith("/inicio")
    assert sb.cadastros[-1] == {"username": "carol", "senha": "12345678", "email": "",
                                "aceitou_localizacao": True}
    assert cliente.get("/inicio").status_code == 200


def test_tela_de_cadastro_nao_pede_email(cliente):
    pagina = html(cliente.get("/cadastro"))
    assert 'name="email"' not in pagina and "adicionar um e-mail depois" in pagina


# ------------------------------------------------------------- servidores
def test_lista_esconde_servidor_hack_para_quem_nao_usa(cliente):
    entrar(cliente)
    pagina = html(cliente.get("/servidores"))
    assert "Corrida Turbo" in pagina and "7/10 jogadores (5 IA)" in pagina and "HACK/MOD</span>" not in pagina
    assert "HACK/MOD</span>" in html(cliente.get("/servidores?todos=1"))


def test_entrar_bloqueado_mostra_motivo(cliente):
    entrar(cliente)
    token = csrf(cliente)
    r = cliente.post("/servidores/s3/entrar", data={"csrf": token},
                     headers={"Referer": "http://localhost/servidores"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/servidores")
    assert "exclusivo para quem usa hack" in html(cliente.get("/servidores"))


def test_servidor_cheio_vai_para_fila(cliente, sb):
    entrar(cliente)
    sb.servidores[0]["capacidade"] = 2
    r = cliente.post("/servidores/s1/entrar", data={"csrf": csrf(cliente)})
    assert r.headers["Location"].endswith("/inicio")
    assert "Na fila de espera — posição 2." in html(cliente.get("/inicio"))


def test_criar_servidor_e_entrar_no_chat(cliente, sb):
    entrar(cliente)
    r = cliente.post("/servidores/criar", data={"gameid": "corrida", "capacidade": "8", "csrf": csrf(cliente)})
    assert r.headers["Location"].endswith("/chat/s9")
    criado = sb.servidores[-1]
    assert criado["host_id"] == "u1" and criado["capacidade"] == 8 and criado["is_hack_server"] is False
    pagina = html(cliente.get("/chat/s9"))
    assert "/api/heartbeat/" in pagina             # host manda heartbeat


def test_capacidade_invalida(cliente):
    entrar(cliente)
    cliente.post("/servidores/criar", data={"gameid": "corrida", "capacidade": "500", "csrf": csrf(cliente)},
                 headers={"Referer": "http://localhost/servidores"})
    assert "entre 1 e 100" in html(cliente.get("/servidores"))


# ------------------------------------------------------------------- chat
def test_chat_completo(cliente, sb):
    entrar(cliente)
    token = csrf(cliente)
    cliente.post("/servidores/s1/entrar", data={"csrf": token})
    assert cliente.get("/inicio").headers["Location"].endswith("/chat/s1")
    pagina = html(cliente.get("/chat/s1"))
    assert "Corrida Turbo" in pagina and "/api/heartbeat/" not in pagina

    r = cliente.post("/api/chat/s1", json={"texto": "que porra de lag"}, headers={"X-CSRF": token})
    assert r.get_json()["resultado"] == "enviada"
    d = cliente.get("/api/chat/s1?depois=1").get_json()
    assert d["ainda_no_servidor"] is True
    assert [m["mensagem_filtrada"] for m in d["mensagens"]] == ["que lag"]

    r = cliente.post("/api/chat/s1", json={"texto": "  "}, headers={"X-CSRF": token})
    assert r.status_code == 400 and "entre 1 e 500" in r.get_json()["mensagem"]

    cliente.post("/chat/s1/sair", data={"csrf": token})
    assert cliente.get("/api/chat/s1").get_json()["ainda_no_servidor"] is False


def test_chat_de_servidor_que_nao_estou_redireciona(cliente):
    entrar(cliente)
    assert cliente.get("/chat/s1").headers["Location"].endswith("/servidores")


def test_api_sem_csrf_recusada(cliente):
    entrar(cliente)
    assert cliente.post("/api/chat/s1", json={"texto": "oi"}).status_code == 400


def test_api_sem_login_responde_401_json(cliente):
    r = cliente.get("/api/status")
    assert r.status_code == 401 and r.get_json()["erro"] == "sessao_expirada"


# ---------------------------------------------------------- alertas/perfil
def test_ver_senha_tentada(cliente, sb):
    entrar(cliente)
    r = cliente.post("/api/alertas/9/senha", json={}, headers={"X-CSRF": csrf(cliente)})
    assert r.get_json() == {"senha": "alice2024"}
    assert sb.alertas[0]["lido"] is True


def test_email_no_perfil_salvar_e_remover(cliente, sb):
    entrar(cliente)
    token = csrf(cliente)
    cliente.post("/perfil", data={"idioma": "pt-BR", "email": "Alice@Ex.com", "csrf": token})
    assert sb.perfil["email"] == "alice@ex.com"
    assert 'value="alice@ex.com"' in html(cliente.get("/perfil"))
    cliente.post("/perfil", data={"idioma": "pt-BR", "email": "", "csrf": token})
    assert sb.perfil["email"] is None
    cliente.post("/perfil", data={"idioma": "pt-BR", "email": "errado", "csrf": token},
                 headers={"Referer": "http://localhost/perfil"})
    assert "E-mail inválido" in html(cliente.get("/perfil"))


def test_salvar_perfil_e_idioma_invalido_vira_padrao(cliente, sb):
    entrar(cliente)
    cliente.post("/perfil", data={"idioma": "klingon", "jogo_mod": "corrida", "csrf": csrf(cliente)})
    assert sb.perfil["idioma"] == "pt-BR"
    assert sb.perfil["jogo_mod"] == "corrida"
    assert sb.perfil["aceitou_localizacao"] is False
    pagina = html(cliente.get("/perfil"))
    assert '<option value="corrida" selected>' in pagina


def test_nome_com_html_e_escapado(cliente, sb):
    sb.perfil["username"] = "<script>x</script>"
    entrar(cliente)
    assert "<script>x</script>" not in html(cliente.get("/inicio"))


def test_backend_nao_configurado_explica_o_erro(cliente, sb):
    sb.request = lambda *a, **k: Resp(404, {"code": "NOT_FOUND", "message": "Requested function was not found"})
    r = entrar(cliente)
    assert "ainda não foi configurado" in html(r)


# ------------------------------------------------------ tickets, ADM, avatar
def test_presente_diario_aparece_uma_vez_e_mostra_tickets(cliente, sb):
    entrar(cliente)
    pagina = html(cliente.get("/inicio"))
    assert "Presente do dia: +5 tickets" in pagina and "Tickets: 5" in pagina
    pagina = html(cliente.get("/inicio"))
    assert "Presente do dia" not in pagina and "Tickets: 5" in pagina


def test_adm_tem_tickets_infinitos_e_aba_adm(cliente, sb):
    sb.perfil["is_adm"] = True
    sb.presente = {"infinito": True, "ganhou": 0}
    entrar(cliente)
    pagina = html(cliente.get("/inicio"))
    assert "∞ (ADM)" in pagina and 'href="/adm"' in pagina
    painel = html(cliente.get("/adm"))
    assert "bob" in painel and "1.2.3.4" in painel and "2 usuários" in painel and "7/10 (5 IA)" in painel


def test_usuario_comum_nao_ve_aba_adm_nem_painel(cliente, sb):
    entrar(cliente)
    assert 'href="/adm"' not in html(cliente.get("/inicio"))
    r = cliente.get("/adm")
    assert r.status_code == 400 and "Apenas adm" in html(r)


def test_acoes_do_adm(cliente, sb):
    sb.perfil["is_adm"] = True
    entrar(cliente)
    token = csrf(cliente)
    for acao, dados in [("tickets", {"user_id": "u9", "quantidade": "10"}),
                        ("banir", {"user_id": "u9", "motivo": "spam"}),
                        ("desbanir", {"user_id": "u9"}),
                        ("definir-adm", {"user_id": "u9", "adm": "1"}),
                        ("desbloquear-ip", {"ip": "1.2.3.4"}),
                        ("encerrar-servidor", {"server_uid": "s1"})]:
        r = cliente.post(f"/adm/{acao}", data=dict(dados, csrf=token))
        assert r.status_code == 302 and r.headers["Location"].endswith("/adm")
    assert [c[0] for c in sb.adm_chamadas] == ["adm_dar_tickets", "adm_banir", "adm_desbanir",
                                                "adm_definir_adm", "adm_desbloquear_ip", "adm_encerrar_servidor"]
    assert sb.adm_chamadas[0][1] == {"p_user": "u9", "p_qtd": 10}
    assert sb.adm_chamadas[3][1] == {"p_user": "u9", "p_adm": True}


def test_salvar_avatar_e_previa(cliente, sb):
    entrar(cliente)
    cliente.post("/perfil", data={"idioma": "pt-BR", "pele": "#8d5524", "cabelo": "moicano",
                                  "cor_cabelo": "#e53935", "camisa": "#43a047", "calca": "#212121",
                                  "acessorio": "coroa", "csrf": csrf(cliente)})
    assert sb.perfil["avatar"] == {"pele": "#8d5524", "cabelo": "moicano", "cor_cabelo": "#e53935",
                                   "camisa": "#43a047", "calca": "#212121", "acessorio": "coroa"}
    svg = cliente.get("/avatar.svg?pele=%238d5524&cabelo=moicano&acessorio=coroa").get_data(as_text=True)
    assert svg.startswith("<svg") and "#8d5524" in svg and "#fbc02d" in svg


def test_avatar_ignora_valores_inventados(cliente, sb):
    entrar(cliente)
    cliente.post("/perfil", data={"idioma": "pt-BR", "pele": "javascript:alert(1)", "cabelo": "<b>",
                                  "csrf": csrf(cliente)})
    assert sb.perfil["avatar"]["pele"] == "#c68642" and sb.perfil["avatar"]["cabelo"] == "curto"


def test_adm_sem_chat_e_banimento_vao_para_o_discord(cliente, sb, monkeypatch):
    import discord_log
    monkeypatch.setenv("ROLOX_WEBHOOK_BANIMENTOS", "https://discord.com/api/webhooks/1/b")
    monkeypatch.setenv("ROLOX_WEBHOOK_PUNICOES", "https://discord.com/api/webhooks/2/p")
    enviados = []
    monkeypatch.setattr(discord_log, "registrar_sync", lambda *a, **k: enviados.append(a) or True)
    sb.perfil["is_adm"] = True
    entrar(cliente)
    token = csrf(cliente)
    cliente.post("/adm/banir", data={"user_id": "u9", "nome": "bob", "motivo": "xingou", "csrf": token})
    cliente.post("/adm/sem-chat", data={"user_id": "u9", "nome": "bob", "minutos": "60", "motivo": "spam", "csrf": token})
    cliente.post("/adm/com-chat", data={"user_id": "u9", "nome": "bob", "csrf": token})
    assert [c[0] for c in sb.adm_chamadas] == ["adm_banir", "adm_sem_chat", "adm_com_chat"]
    assert sb.adm_chamadas[1][1] == {"p_user": "u9", "p_minutos": 60, "p_motivo": "spam"}
    assert enviados == [("ban", "bob", "xingou", "alice (ADM)", "Jogo ROLOX", None),
                        ("sem_chat", "bob", "spam", "alice (ADM)", "Jogo ROLOX", 60),
                        ("com_chat", "bob", "chat liberado pelo ADM", "alice (ADM)", "Jogo ROLOX", None)]
    # ao abrir o painel, o IP bloqueado que ainda não foi pro Discord é registrado e marcado
    enviados.clear()
    cliente.get("/adm")
    assert enviados and enviados[0][0] == "ip_bloqueado"
    assert ("adm_marcar_ip_registrado", {"p_ip": "1.2.3.4"}) in sb.adm_chamadas



# ------------------------------------------------------------ Studio
class StudioFalso:
    """Imita o servidor do ROLOX Studio (Rolox-Studio/servidor.py) em localhost:8600."""

    def __init__(self, ligado=True, projetos=None):
        self.ligado = ligado
        self.lista = projetos if projetos is not None else []
        self.pedidos = []

    def get(self, url, timeout=None):
        import requests
        self.pedidos.append(url)
        if not self.ligado:
            raise requests.ConnectionError("recusado")
        caminho = urlsplit(url).path
        if caminho == "/":
            r = Resp(200)
            r.text = "<title>Rolox Studio</title>"
            return r
        if caminho == "/api/projetos":
            return Resp(200, self.lista)
        return Resp(404)


def cliente_com_studio(sb, studio):
    from studio_local import StudioLocal
    app = criar_app(lambda s: RoloxAPI(s, url="https://falso", chave="k", http=sb), segredo="teste",
                    studio=StudioLocal("http://localhost:8600", http=studio))
    app.testing = True
    return app.test_client()


def test_studio_precisa_de_login(sb):
    c = cliente_com_studio(sb, StudioFalso())
    r = c.get("/studio")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_studio_desligado_mostra_como_ligar(sb):
    studio = StudioFalso(ligado=False)
    c = cliente_com_studio(sb, studio)
    entrar(c)
    t = html(c.get("/studio"))
    assert "Studio desligado" in t and "python servidor.py" in t and "pip install -r requirements.txt" in t
    assert "Tentar de novo" in t and studio.pedidos == ["http://localhost:8600/"]


def test_studio_ligado_mostra_modelos_e_projetos(sb):
    studio = StudioFalso(projetos=[{"nome": "meu_jogo", "tamanho": 5120},
                                   {"nome": "../segredo", "tamanho": 10},     # nome inválido: some
                                   "lixo"])
    c = cliente_com_studio(sb, studio)
    entrar(c)
    t = html(c.get("/studio"))
    assert "Studio ligado em http://localhost:8600" in t
    assert 'href="http://localhost:8600/studio/leve"' in t and 'href="http://localhost:8600/studio/pc"' in t
    for modelo in ("vazio", "obby", "moedas"):
        assert f"/studio/leve?modelo={modelo}" in t
    assert "/studio/leve?projeto=meu_jogo" in t and "5 KB" in t
    assert "segredo" not in t
    assert 'class="ativo"><span>🧱</span>Studio' in t


def test_studio_ligado_sem_projetos(sb):
    c = cliente_com_studio(sb, StudioFalso(projetos=[]))
    entrar(c)
    assert "Nenhum projeto salvo ainda" in html(c.get("/studio"))


def test_studio_url_valida_nomes():
    from studio_local import StudioLocal
    s = StudioLocal("http://localhost:8600/")
    assert s.url("pc") == "http://localhost:8600/studio/pc"
    assert s.url("leve", projeto="Jogo-1") == "http://localhost:8600/studio/leve?projeto=Jogo-1"
    for ruim in (dict(modo="x"), dict(projeto="../a"), dict(modelo="nao-existe")):
        with pytest.raises(ValueError):
            s.url(**{"modo": "leve", **ruim})


def test_aba_studio_aparece_para_todos(cliente):
    entrar(cliente)
    t = html(cliente.get("/inicio"))
    assert "<span>🧱</span>Studio" in t


# ------------------------------------------------------------ Render
def test_saude(cliente):
    assert cliente.get("/saude").get_data(as_text=True) == "ok"


def test_render_manda_ip_do_jogador_com_a_chave(sb, monkeypatch):
    monkeypatch.setenv("ROLOX_IP_CABECALHO", "CF-Connecting-IP")
    app = criar_app(lambda s: RoloxAPI(s, url="https://falso", chave="k", http=sb, chave_proxy="K1"),
                    segredo="teste")
    app.testing = True
    c = app.test_client()
    tok = csrf(c)
    c.post("/login", data={"usuario": "Alice", "senha": "certa", "csrf": tok},
           headers={"CF-Connecting-IP": "200.10.20.30"})
    _, caminho, _, _, cab = next(x for x in sb.chamadas if x[1] == "/functions/v1/login-protegido")
    assert cab["x-rolox-proxy-chave"] == "K1" and cab["x-rolox-ip-cliente"] == "200.10.20.30"
    # IP inválido no cabeçalho: vai vazio (a Edge Function recusa em vez de usar o IP do servidor)
    sb.chamadas.clear()
    c.post("/login", data={"usuario": "Alice", "senha": "certa", "csrf": tok},
           headers={"CF-Connecting-IP": "1.2.3.4; drop"})
    _, _, _, _, cab = next(x for x in sb.chamadas if x[1] == "/functions/v1/login-protegido")
    assert cab["x-rolox-ip-cliente"] == ""


def test_sem_chave_nao_manda_cabecalhos_do_proxy(cliente, sb):
    entrar(cliente)
    _, _, _, _, cab = next(x for x in sb.chamadas if x[1] == "/functions/v1/login-protegido")
    assert "x-rolox-proxy-chave" not in cab and "x-rolox-ip-cliente" not in cab
    # e a chave nunca vai para o REST do banco
    assert all("x-rolox-proxy-chave" not in (x[4] or {}) for x in sb.chamadas if x[1].startswith("/rest/"))


def test_studio_no_site_e_o_navegador_que_procura(sb):
    from studio_local import StudioLocal
    studio = StudioFalso()
    app = criar_app(lambda s: RoloxAPI(s, url="https://falso", chave="k", http=sb), segredo="teste",
                    studio=StudioLocal("http://localhost:8600", http=studio), studio_no_navegador=True)
    app.testing = True
    c = app.test_client()
    entrar(c)
    t = html(c.get("/studio"))
    assert studio.pedidos == []                         # o servidor não procura nada
    assert "Procurando o Studio neste aparelho" in t and "fetch(BASE + '/api/projetos'" in t
    assert "/studio/leve?modelo=obby" in t and "python servidor.py" in t


# ------------------------------------------------ Studio dentro do site
def test_studio_dentro_do_site(cliente, sb):
    assert cliente.get("/studio/leve").status_code == 302          # precisa entrar
    entrar(cliente)
    t = html(cliente.get("/studio"))
    assert "roda aqui no site" in t and 'href="/studio/leve?modelo=obby"' in t
    ed = cliente.get("/studio/leve")
    assert ed.status_code == 200 and "ROLOX Studio" in html(ed)
    assert cliente.get("/static/studio/editor.js").status_code == 200
    assert cliente.get("/static/vendor/fengari/fengari-web.js").status_code == 200
    assert cliente.get("/static/rolox.css").status_code == 200       # o CSS do app continua
    assert cliente.get("/studio/xyz").status_code == 404


def test_projetos_do_studio_na_conta(cliente, sb):
    entrar(cliente)
    proj = {"formato": "rolox-studio", "versao": 1, "pecas": []}
    r = cliente.put("/api/projetos/meu_obby", json=proj)
    assert r.status_code == 200 and sb.projetos["meu_obby"]["dados"] == proj
    assert cliente.get("/api/projetos").get_json() == [{"nome": "meu_obby", "tamanho": sb.projetos["meu_obby"]["tamanho"]}]
    assert cliente.get("/api/projetos/meu_obby").get_json() == proj
    assert cliente.get("/api/projetos/outro").status_code == 404
    assert cliente.put("/api/projetos/..%2Fx", json=proj).status_code in (400, 404)
    assert cliente.put("/api/projetos/a", json={"x": 1}).status_code == 400
    assert cliente.put("/api/projetos/a", data="formato=rolox-studio").status_code == 415
    assert "meu_obby" in html(cliente.get("/studio"))


# ------------------------------------------ mapas no bucket / dono / jogos com chat
PROJETO = {"formato": "rolox-studio", "versao": 1, "nome": "Obby", "servicos": {}}


def enviar_mapa(cliente, **extra):
    tok = csrf(cliente)
    return cliente.post("/api/mapas/enviar", json={"nome": "Obby da lava", "descricao": "pule!", "projeto": PROJETO, **extra},
                        headers={"X-CSRF": tok})


def test_enviar_mapa_vai_para_o_bucket_e_fica_em_analise(cliente, sb):
    entrar(cliente)
    r = enviar_mapa(cliente)
    assert r.status_code == 200, r.get_data(as_text=True)
    mid = r.get_json()["id"]
    (caminho, conteudo), = sb.arquivos.items()
    assert caminho.startswith(f"u1/{mid}/") and caminho.endswith(".json")
    assert json.loads(conteudo) == PROJETO
    assert sb.mapas[mid]["status"] == "em_analise"
    # reenviar com o mesmo id: mesma entrada, versão nova
    r2 = enviar_mapa(cliente, mapa_id=mid)
    assert r2.get_json()["id"] == mid and len(sb.arquivos) == 2 and len(sb.mapas) == 1
    t = html(cliente.get("/jogos"))
    assert "Obby da lava" in t and "EM ANÁLISE" in t and "Nenhum jogo aprovado ainda" in t


def test_enviar_mapa_recusa_lixo_e_sem_csrf(cliente, sb):
    entrar(cliente)
    tok = csrf(cliente)
    assert cliente.post("/api/mapas/enviar", json={"nome": "x", "projeto": PROJETO}).status_code == 400
    r = cliente.post("/api/mapas/enviar", json={"nome": "x", "projeto": {"oi": 1}}, headers={"X-CSRF": tok})
    assert r.status_code == 400 and "não é um mapa" in r.get_json()["mensagem"]
    assert sb.arquivos == {}


def test_so_o_dono_ve_o_painel_e_aprova(cliente, sb):
    entrar(cliente)
    mid = enviar_mapa(cliente).get_json()["id"]
    assert cliente.get("/dono").status_code == 403
    assert "<span>👑</span>Dono" not in html(cliente.get("/jogos"))
    tok = csrf(cliente)
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    assert sb.mapas[mid]["status"] == "em_analise"                      # o banco recusou (não é dono)
    sb.dono = True
    t = html(cliente.get("/dono"))
    assert "Obby da lava" in t and f"/jogar/{mid}?teste=1" in t and "<span>👑</span>Dono" in t
    # dono testa a versão em análise no próprio app
    t = html(cliente.get(f"/jogar/{mid}?teste=1"))
    assert "Modo teste" in t and f"/api/mapas/{mid}/dados?versao=enviada" in t and 'id="painelChat"' not in t
    assert json.loads(cliente.get(f"/api/mapas/{mid}/dados?versao=enviada").get_data()) == PROJETO
    assert cliente.get(f"/api/mapas/{mid}/dados").status_code == 404     # ainda não tem versão aprovada
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    assert sb.mapas[mid]["status"] == "aprovado"


def test_jogo_aprovado_todos_jogam_com_chat(cliente, sb):
    entrar(cliente)
    mid = enviar_mapa(cliente).get_json()["id"]
    sb.dono = True
    tok = csrf(cliente)
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    sb.dono = False
    t = html(cliente.get("/jogos"))
    assert "Obby da lava" in t and f"/jogos/{mid}/jogar" in t and f"id=\"mapa-{mid}\"" in t
    r = cliente.post(f"/jogos/{mid}/jogar", data={"csrf": tok})
    assert r.status_code == 302 and f"/jogar/{mid}?s=s9" in r.headers["Location"]
    novo = next(s for s in sb.servidores if s["server_uid"] == "s9")
    assert novo["gameid"] == sb.mapas[mid]["gameid"] and novo["capacidade"] == 10
    t = html(cliente.get(f"/jogar/{mid}?s=s9"))
    assert "painelChat" in t and "/api/chat/" in t and f"/api/mapas/{mid}/dados?versao=aprovada" in t
    assert "/static/studio/jogar.js" in t
    assert json.loads(cliente.get(f"/api/mapas/{mid}/dados?versao=aprovada").get_data()) == PROJETO
    # chat do servidor do jogo
    cliente.post("/api/chat/s9", json={"texto": "bora!"}, headers={"X-CSRF": tok})
    assert any(m["mensagem_filtrada"] == "bora!" for m in sb.chat)
    # segundo jogador entra no MESMO servidor (tem vaga)
    sb.membros["s9"] = ["u7"]
    r = cliente.post(f"/jogos/{mid}/jogar", data={"csrf": tok})
    assert "s=s9" in r.headers["Location"]
    # sair volta para Jogos
    r = cliente.post("/chat/s9/sair", data={"csrf": tok, "voltar": "jogos"})
    assert r.headers["Location"].endswith("/jogos")


def test_jogar_mapa_alheio_nao_aprovado_e_id_invalido(cliente, sb):
    entrar(cliente)
    sb.mapas["11111111-1111-1111-1111-111111111111"] = {
        "id": "11111111-1111-1111-1111-111111111111", "autor_id": "u5", "nome": "x", "descricao": "",
        "status": "em_analise", "motivo": None, "gameid": None, "caminho_enviado": "u5/a/b.json",
        "caminho_aprovado": None, "enviado_em": "", "aprovado_em": None}
    assert cliente.get("/jogar/11111111-1111-1111-1111-111111111111?teste=1").status_code == 403
    assert cliente.get("/jogar/11111111-1111-1111-1111-111111111111").status_code == 404
    assert cliente.get("/jogar/nao-e-uuid").status_code == 404


def test_cadastro_com_codigo_do_dono(cliente, sb):
    t = html(cliente.get("/cadastro?dono=1"))
    assert 'name="codigo_dono"' in t
    assert 'name="codigo_dono"' not in html(cliente.get("/cadastro"))
    tok = csrf(cliente)
    cliente.post("/cadastro", data={"usuario": "arthurdevpromax.off_dono", "senha": "segredo123",
                                    "codigo_dono": " ROLOX-AAAA-BBBB ", "csrf": tok})
    _, _, _, corpo, _ = next(x for x in sb.chamadas if x[1] == "/functions/v1/cadastro")
    assert corpo["username"] == "arthurdevpromax.off_dono" and corpo["codigo_dono"] == "ROLOX-AAAA-BBBB"


def test_multijogador_dois_jogadores_se_veem(cliente, sb, tmp_path, monkeypatch):
    monkeypatch.setenv("ROLOX_PASTA_SALAS", str(tmp_path))
    entrar(cliente)
    mid = enviar_mapa(cliente).get_json()["id"]
    sb.dono = True
    tok = csrf(cliente)
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    cliente.post(f"/jogos/{mid}/jogar", data={"csrf": tok})
    t = html(cliente.get(f"/jogar/{mid}?s=s9"))
    passe = re.search(r'passe: ("[^"]+")', t).group(1).strip('"')
    assert "Multijogador" in t
    r = cliente.post("/api/sala", json={"passe": passe, "p": [1, 2, 3]}, headers={"X-CSRF": tok})
    assert r.status_code == 200 and r.get_json() == {"jogadores": []}
    # passe falso / sem CSRF
    assert cliente.post("/api/sala", json={"passe": passe + "x", "p": [0, 0, 0]}, headers={"X-CSRF": tok}).status_code == 403
    assert cliente.post("/api/sala", json={"passe": passe}).status_code == 400
    # outro jogador (outro processo do site) entra na mesma sala
    import multijogador
    outro = multijogador.Passes("teste").criar("s9", "u7", "bob", {"camisa": "#e53935"})
    multijogador.Salas(tmp_path).atualizar(multijogador.Passes("teste").ler(outro), {"p": [9, 0, 9], "m": True})
    j = cliente.post("/api/sala", json={"passe": passe, "p": [1, 2, 3]}, headers={"X-CSRF": tok}).get_json()["jogadores"]
    assert j[0]["n"] == "bob" and j[0]["p"] == [9.0, 0.0, 9.0]
    assert cliente.post("/api/sala/sair", data={"passe": passe, "csrf": tok}).status_code == 204


def test_curtir_e_visitas_mais_jogados(cliente, sb):
    entrar(cliente)
    tok = csrf(cliente)
    sb.dono = True
    ids = []
    for nome in ("Obby A", "Obby B"):
        mid = cliente.post("/api/mapas/enviar", json={"nome": nome, "projeto": PROJETO}, headers={"X-CSRF": tok}).get_json()["id"]
        cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
        ids.append(mid)
    # B é jogado (visita conta 1x) e curtido
    cliente.post(f"/jogos/{ids[1]}/jogar", data={"csrf": tok})
    cliente.post(f"/jogos/{ids[1]}/jogar", data={"csrf": tok})
    assert sb.mapas[ids[1]]["visitas"] == 1
    r = cliente.post(f"/jogos/{ids[1]}/curtir", data={"csrf": tok, "curtir": "1"})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"#mapa-{ids[1]}")
    t = html(cliente.get("/jogos"))
    assert t.index("Obby B") < t.index("Obby A")                 # mais jogado primeiro
    assert "👁 1 · ❤ 1" in t and "❤️" in t and "🔥 Mais jogados" in t
    # pelo jogo (JSON): descurtir
    assert cliente.post(f"/jogos/{ids[1]}/curtir", json={"curtir": False}, headers={"X-CSRF": tok}).get_json()["curtidas"] == 0
    t = html(cliente.get(f"/jogar/{ids[1]}?s=s9"))
    assert 'id="curtir" data-curti="0"' in t


def test_placar_recorde_e_ranking(cliente, sb):
    entrar(cliente)
    tok = csrf(cliente)
    mid = cliente.post("/api/mapas/enviar", json={"nome": "Moedas", "projeto": PROJETO}, headers={"X-CSRF": tok}).get_json()["id"]
    # ainda não aprovado: o banco recusa
    assert cliente.post(f"/api/placar/{mid}", json={"estatistica": "Moedas", "valor": 3}, headers={"X-CSRF": tok}).status_code == 400
    sb.dono = True
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    for v in (3, 8, 2):
        cliente.post(f"/api/placar/{mid}", json={"estatistica": "Moedas", "valor": v}, headers={"X-CSRF": tok})
    r = cliente.get(f"/api/placar/{mid}").get_json()
    assert r[0] == {"pos": 1, "nome": "alice", "estatistica": "Moedas", "valor": 8.0, "eu": True}
    assert r[1]["nome"] == "bob" and r[1]["eu"] is False
    for ruim in ({"valor": -1}, {"valor": "abc"}, {"valor": 1e13}, {}):
        assert cliente.post(f"/api/placar/{mid}", json=ruim, headers={"X-CSRF": tok}).status_code == 400
    t = html(cliente.get(f"/jogar/{mid}?teste=1"))
    assert "enviar: null" in t and "abrirRanking" in t          # modo teste não conta recorde
    cliente.post(f"/jogos/{mid}/jogar", data={"csrf": tok})
    t = html(cliente.get(f"/jogar/{mid}?s=s9"))
    assert f"/api/placar/{mid}" in t and "enviar: (estatistica, valor) =>" in t


def test_amigos_pedir_aceitar_e_entrar_junto(cliente, sb):
    entrar(cliente)
    tok = csrf(cliente)
    r = cliente.post("/amigos/pedir", data={"csrf": tok, "usuario": " Bob "})
    assert r.status_code == 302 and sb.amizade_chamadas[-1] == ("pedir_amizade", {"p_username": "bob"})
    cliente.post("/amigos/pedir", data={"csrf": tok, "usuario": "fantasma"})
    assert "jogador não encontrado" in html(cliente.get("/amigos")).lower()
    bob = "22222222-2222-2222-2222-222222222222"
    sb.amigos = [{"id": bob, "username": "bob", "tipo": "recebido", "avatar": {}, "online": False}]
    assert "quer ser seu amigo" in html(cliente.get("/amigos"))
    cliente.post(f"/amigos/{bob}/aceitar", data={"csrf": tok})
    assert sb.amizade_chamadas[-1] == ("responder_amizade", {"p_de": bob, "p_aceitar": True})
    # bob jogando um mapa: aparece no Início com "Entrar junto"
    mid = cliente.post("/api/mapas/enviar", json={"nome": "Obby", "projeto": PROJETO}, headers={"X-CSRF": tok}).get_json()["id"]
    sb.dono = True
    cliente.post(f"/dono/{mid}/aprovar", data={"csrf": tok})
    sb.servidores.append({"server_uid": "s5", "gameid": sb.mapas[mid]["gameid"], "host_id": "u2", "capacidade": 10,
                          "is_hack_server": False, "status": "aberto"})
    sb.membros["s5"] = ["u2"]
    sb.amigos = [{"id": bob, "username": "bob", "tipo": "amigo", "avatar": {}, "online": True,
                  "server_uid": "s5", "jogo": "Obby", "mapa_id": mid}]
    t = html(cliente.get("/inicio"))
    assert "jogando Obby" in t and "/amigos/entrar/s5" in t
    r = cliente.post("/amigos/entrar/s5", data={"csrf": tok})
    assert r.headers["Location"].endswith(f"/jogar/{mid}?s=s5")
    # já no jogo: Início leva de volta ao JOGO (não ao chat antigo)
    assert cliente.get("/inicio").headers["Location"].endswith(f"/jogar/{mid}?s=s5")
    assert cliente.get("/api/status").get_json()["destino"].endswith(f"/jogar/{mid}?s=s5")
    # servidor que o amigo não está: recusa
    assert cliente.post("/amigos/entrar/s1", data={"csrf": tok}).headers["Location"].endswith("/amigos")
    cliente.post(f"/amigos/{bob}/desfazer", data={"csrf": tok})
    assert sb.amizade_chamadas[-1] == ("desfazer_amizade", {"p_outro": bob})
    assert cliente.post("/amigos/nao-uuid/aceitar", data={"csrf": tok}).status_code == 404


def test_entrar_pelo_app_vai_direto_para_o_jogo(sb):
    app = criar_app(lambda s: RoloxAPI(s, url="https://falso", chave="k", http=sb), segredo="teste")
    app.testing = True
    c = app.test_client()
    t = html(c.get("/app/entrar"))
    assert "history.replaceState" in t and "/api/app/sessao" in t
    tok = csrf(c)
    assert c.post("/api/app/sessao", json={"token": "T1"}).status_code == 400          # sem CSRF
    r = c.post("/api/app/sessao", json={"token": "errado"}, headers={"X-CSRF": tok})
    assert r.status_code == 401
    r = c.post("/api/app/sessao", json={"token": "T1"}, headers={"X-CSRF": tok})
    assert r.get_json() == {"username": "alice"}
    with c.session_transaction() as sess:
        assert sess["sb"] == {"access_token": "T1", "refresh_token": "", "user_id": "u1"}
    assert c.get("/jogos").status_code == 200                                    # já logado
    # token do app venceu: sem refresh, o site pede login (não fica em loop)
    sb.token_valido = "T2"
    assert "/login" in c.get("/jogos").headers["Location"]
