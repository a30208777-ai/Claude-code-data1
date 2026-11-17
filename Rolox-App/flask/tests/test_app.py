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
                       "jogo_mod": None, "aceitou_localizacao": True, "banido": False}
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

    def onde(self):
        return next((s for s, m in self.membros.items() if "u1" in m), None)

    def request(self, metodo, url, json=None, params=None, headers=None, timeout=None):
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
        if p == "/rest/v1/perfis":
            if metodo == "PATCH":
                self.perfil.update(json)
            return Resp(200, [self.perfil])
        if p == "/rest/v1/jogos":
            return Resp(200, self.jogos)
        if p == "/rest/v1/servidores_ativos":
            if metodo == "GET":
                return Resp(200, [dict(s, users_dos_servidores=[{"count": len(self.membros.get(s["server_uid"], []))}])
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
    assert "Corrida Turbo" in pagina and "2/10 jogadores" in pagina and "HACK/MOD</span>" not in pagina
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
