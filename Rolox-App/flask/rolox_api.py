"""Cliente do Supabase para o Rolox (versão Flask, síncrona, só `requests`).

Mesmas regras do app Flet: o celular acessa direto as tabelas do Supabase
(protegidas por RLS) e o login passa pela Edge Function `login-protegido`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

import avatar as avatar_mod

SUPABASE_URL = os.environ.get("ROLOX_SUPABASE_URL", "https://llgriaqnlcylpaxudrlg.supabase.co")
# publishable key: pública por natureza (só dá o acesso que o RLS permite). Nunca a service_role.
SUPABASE_CHAVE = os.environ.get("ROLOX_SUPABASE_CHAVE", "sb_publishable_GFKzsWxgUtXTff5fHWVVfQ_dUKdF62n")

USERNAME_VALIDO = re.compile(r"^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$")
EMAIL_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MENSAGENS = {
    "credenciais_invalidas": "Usuário ou senha incorretos.",
    "ip_bloqueado": "Este aparelho/rede foi bloqueado após 3 senhas erradas.",
    "conta_banida": "Esta conta foi banida por um moderador.",
    "email_nao_confirmado": "Confirme seu e-mail (veja a caixa de entrada) antes de entrar.",
    "confirme_por_email": "Muitas tentativas. Enviamos um e-mail para você redefinir a senha.",
    "dados_invalidos": "Preencha usuário e senha.",
    "username_invalido": "O usuário deve ter 3 a 32 letras minúsculas, números ou hífen "
                         "(sem hífen no começo ou no fim).",
    "senha_curta": "A senha precisa ter pelo menos 8 caracteres.",
    "email_invalido": "E-mail inválido.",
    "senha_fraca": "Senha fraca demais. Use letras e números.",
    "erro_cadastro": "Não foi possível criar a conta agora. Tente de novo.",
    "muitas_tentativas": "Muitas senhas erradas. Espere um pouco e tente de novo.",
    "username_em_uso": "Esse nome de usuário já está em uso.",
    "sessao_expirada": "Sua sessão expirou. Entre novamente.",
    "sem_conexao": "Sem conexão com o servidor. Verifique sua internet.",
    "NOT_FOUND": "O servidor do Rolox ainda não foi configurado no Supabase "
                 "(função de login não encontrada).",
    "PGRST205": "O banco do Rolox ainda não foi configurado no Supabase (tabela não encontrada).",
    "servidor_inexistente": "Esse servidor não existe mais.",
    "use_servidor_hack": "Você marcou hack/mod neste jogo. Entre em um servidor de hack.",
    "servidor_so_para_hack": "Servidor exclusivo para quem usa hack/mod neste jogo.",
    "fora_do_servidor": "Você não está neste servidor.",
    "muito_rapido": "Calma! Espere um segundo entre as mensagens.",
    "tamanho_invalido": "A mensagem deve ter entre 1 e 500 caracteres.",
    "alerta_nao_encontrado": "Alerta não encontrado.",
    "capacidade_invalida": "A capacidade deve ficar entre 1 e 100.",
    "quantidade_invalida": "Digite um número de tickets válido.",
    "42501": "Você não tem permissão para isso.",
}


class ErroRolox(Exception):
    def __init__(self, codigo: str, detalhes: Optional[dict] = None):
        self.codigo = codigo
        self.detalhes = detalhes or {}
        super().__init__(codigo)

    @property
    def mensagem(self) -> str:
        if self.codigo == "sem_chat":
            ate = str(self.detalhes.get("ate") or "")
            hora = ate[11:16] if len(ate) >= 16 else ""
            return (f"🔇 Você está sem chat{' até ' + hora + ' (UTC)' if hora else ''}. "
                    f"Motivo: {self.detalhes.get('motivo') or 'sem motivo'}.")
        if self.codigo in ("P0001", "42501") and self.detalhes.get("message"):
            return str(self.detalhes["message"]).capitalize() + "."
        texto = MENSAGENS.get(self.codigo, f"Erro: {self.codigo}")
        restantes = self.detalhes.get("tentativas_restantes")
        if restantes is not None:
            texto += f" Tentativas restantes: {restantes}."
        return texto


@dataclass
class Sessao:
    access_token: str
    refresh_token: str
    user_id: str

    def para_dict(self) -> dict:
        return {"access_token": self.access_token, "refresh_token": self.refresh_token,
                "user_id": self.user_id}

    @classmethod
    def de_dict(cls, d: Optional[dict]) -> Optional["Sessao"]:
        if not d:
            return None
        return cls(d["access_token"], d["refresh_token"], d["user_id"])


class RoloxAPI:
    RESULTADOS_OK = {"entrou", "ja_esta", "fila", "saiu", "enviada"}

    def __init__(self, sessao: Optional[Sessao] = None, *, url: str = SUPABASE_URL,
                 chave: str = SUPABASE_CHAVE, http: Optional[requests.Session] = None,
                 timeout: float = 15, chave_proxy: Optional[str] = None):
        self.sessao = sessao
        # Site no Render: o IP real do jogador vai para as Edge Functions com esta chave
        self.chave_proxy = chave_proxy if chave_proxy is not None else os.environ.get("ROLOX_PROXY_CHAVE", "")
        self.ip_cliente: Optional[str] = None
        self.url = url.rstrip("/")
        self.chave = chave
        self.http = http or requests.Session()
        self.timeout = timeout

    # ------------------------------------------------------------- base
    @property
    def user_id(self) -> str:
        if not self.sessao:
            raise ErroRolox("sessao_expirada")
        return self.sessao.user_id

    def _req(self, metodo: str, caminho: str, *, json: Any = None, params: Optional[dict] = None,
             autenticado: bool = True, prefer: Optional[str] = None,
             renovar_se_expirado: bool = True) -> Any:
        cab = {"apikey": self.chave, "Content-Type": "application/json"}
        if autenticado:
            if not self.sessao:
                raise ErroRolox("sessao_expirada")
            cab["Authorization"] = f"Bearer {self.sessao.access_token}"
        if prefer:
            cab["Prefer"] = prefer
        if self.chave_proxy and caminho.startswith("/functions/v1/"):
            cab["x-rolox-proxy-chave"] = self.chave_proxy
            cab["x-rolox-ip-cliente"] = self.ip_cliente or ""
        try:
            r = self.http.request(metodo, self.url + caminho, json=json, params=params,
                                  headers=cab, timeout=self.timeout)
        except requests.RequestException as e:
            raise ErroRolox("sem_conexao") from e

        if r.status_code == 401 and autenticado and renovar_se_expirado and self.sessao:
            self.renovar()
            return self._req(metodo, caminho, json=json, params=params, autenticado=True,
                             prefer=prefer, renovar_se_expirado=False)

        if r.status_code >= 400:
            try:
                corpo = r.json()
            except ValueError:
                corpo = {}
            if not isinstance(corpo, dict):
                corpo = {}
            codigo = (corpo.get("erro") or corpo.get("error_code") or corpo.get("code")
                      or corpo.get("error") or f"http_{r.status_code}")
            raise ErroRolox(str(codigo), corpo)
        if not r.content:
            return None
        return r.json()

    def _rpc(self, nome: str, **args) -> dict:
        dados = self._req("POST", f"/rest/v1/rpc/{nome}", json=args)
        if dados.get("resultado") not in self.RESULTADOS_OK:
            raise ErroRolox(str(dados.get("resultado")), dados)
        return dados

    # ------------------------------------------------------------ conta
    def login(self, username: str, senha: str) -> Sessao:
        username = (username or "").strip().lower()
        if not username or not senha:
            raise ErroRolox("dados_invalidos")
        d = self._req("POST", "/functions/v1/login-protegido",
                      json={"username": username, "senha": senha}, autenticado=False)
        self.sessao = Sessao(d["access_token"], d["refresh_token"], d["user_id"])
        return self.sessao

    def cadastrar(self, username: str, senha: str, aceitou_localizacao: bool,
                  email: str = "") -> Sessao:
        """Cria a conta (e-mail opcional) e já entra nela."""
        username = (username or "").strip().lower()
        email = (email or "").strip().lower()
        if not USERNAME_VALIDO.match(username):
            raise ErroRolox("username_invalido")
        if len(senha or "") < 8:
            raise ErroRolox("senha_curta")
        if email and not EMAIL_VALIDO.match(email):
            raise ErroRolox("email_invalido")
        d = self._req("POST", "/functions/v1/cadastro", autenticado=False, json={
            "username": username, "senha": senha, "email": email,
            "aceitou_localizacao": aceitou_localizacao})
        self.sessao = Sessao(d["access_token"], d["refresh_token"], d["user_id"])
        return self.sessao

    def renovar(self) -> Sessao:
        if not self.sessao:
            raise ErroRolox("sessao_expirada")
        try:
            d = self._req("POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
                          json={"refresh_token": self.sessao.refresh_token}, autenticado=False)
        except ErroRolox as e:
            if e.codigo == "sem_conexao":
                raise
            self.sessao = None
            raise ErroRolox("sessao_expirada") from e
        self.sessao = Sessao(d["access_token"], d["refresh_token"], d["user"]["id"])
        return self.sessao

    def sair_da_conta(self) -> None:
        if self.sessao:
            try:
                self._req("POST", "/auth/v1/logout", renovar_se_expirado=False)
            except ErroRolox:
                pass
        self.sessao = None

    # ----------------------------------------------------------- perfil
    def meu_perfil(self) -> dict:
        linhas = self._req("GET", "/rest/v1/perfis", params={
            "id": f"eq.{self.user_id}",
            "select": "id,username,email,idioma,jogo_mod,aceitou_localizacao,banido,"
                      "is_adm,tickets,tickets_ultimo_ganho,avatar"})
        if not linhas:
            raise ErroRolox("perfil_nao_encontrado")
        return linhas[0]

    # ------------------------------------------------ projetos do Studio
    def projetos_listar(self) -> list[dict]:
        return self._req("GET", "/rest/v1/projetos_studio", params={
            "select": "nome,tamanho,atualizado_em", "order": "atualizado_em.desc"}) or []

    def projeto_abrir(self, nome: str) -> Optional[dict]:
        linhas = self._req("GET", "/rest/v1/projetos_studio", params={
            "select": "dados", "nome": f"eq.{nome}", "limit": "1"}) or []
        return linhas[0]["dados"] if linhas else None

    def projeto_salvar(self, nome: str, dados: dict, tamanho: int) -> None:
        self._req("POST", "/rest/v1/projetos_studio", params={"on_conflict": "user_id,nome"},
                  prefer="resolution=merge-duplicates,return=minimal",
                  json={"user_id": self.user_id, "nome": nome, "dados": dados, "tamanho": tamanho,
                        "atualizado_em": datetime.now(timezone.utc).isoformat()})

    def atualizar_perfil(self, **campos: Any) -> dict:
        invalidos = set(campos) - {"idioma", "jogo_mod", "aceitou_localizacao", "email", "avatar"}
        if invalidos:
            raise ValueError(f"campos não editáveis: {sorted(invalidos)}")
        if "avatar" in campos:
            campos["avatar"] = avatar_mod.normalizar(campos["avatar"])
        if "email" in campos:
            campos["email"] = (campos["email"] or "").strip().lower() or None
            if campos["email"] and not EMAIL_VALIDO.match(campos["email"]):
                raise ErroRolox("email_invalido")
        linhas = self._req("PATCH", "/rest/v1/perfis", params={"id": f"eq.{self.user_id}"},
                           json=campos, prefer="return=representation")
        return linhas[0] if linhas else {}

    def jogos(self) -> list[dict]:
        return self._req("GET", "/rest/v1/jogos", params={"select": "gameid,nome", "order": "nome"},
                         autenticado=self.sessao is not None)

    # ------------------------------------------------------- servidores
    def servidores(self) -> list[dict]:
        linhas = self._req("GET", "/rest/v1/servidores_ativos", params={
            "select": "server_uid,gameid,host_id,capacidade,is_hack_server,status,"
                      "users_dos_servidores(count),bots_dos_servidores(count)",
            "status": "neq.encerrando", "order": "criado_em.desc", "limit": "100"})
        for s in linhas:
            contagem = s.pop("users_dos_servidores", None) or [{"count": 0}]
            s["humanos"] = contagem[0].get("count", 0)
            ias = s.pop("bots_dos_servidores", None) or [{"count": 0}]
            s["ias"] = ias[0].get("count", 0)
            s["jogadores"] = s["humanos"] + s["ias"]
        return linhas

    def servidor(self, server_uid: str) -> Optional[dict]:
        return next((s for s in self.servidores() if s["server_uid"] == server_uid), None)

    def criar_servidor(self, gameid: str, capacidade: int, hack: bool) -> dict:
        if not 1 <= capacidade <= 100:
            raise ErroRolox("capacidade_invalida")
        return self._req("POST", "/rest/v1/servidores_ativos", prefer="return=representation", json={
            "gameid": gameid, "host_id": self.user_id, "capacidade": capacidade,
            "is_hack_server": hack})[0]

    def heartbeat(self, server_uid: str) -> None:
        self._req("PATCH", "/rest/v1/servidores_ativos",
                  params={"server_uid": f"eq.{server_uid}", "host_id": f"eq.{self.user_id}"},
                  json={"ultimo_heartbeat": datetime.now(timezone.utc).isoformat()})

    def entrar(self, server_uid: str) -> dict:
        return self._rpc("entrar_servidor", p_server=server_uid)

    def sair(self, server_uid: str) -> dict:
        return self._rpc("sair_servidor", p_server=server_uid)

    def onde_estou(self) -> dict:
        uid = self.user_id
        dentro = self._req("GET", "/rest/v1/users_dos_servidores",
                           params={"user_id": f"eq.{uid}", "select": "server_uid"})
        if dentro:
            return {"servidor": dentro[0]["server_uid"], "fila": None, "posicao": None}
        fila = self._req("GET", "/rest/v1/espera",
                         params={"user_id": f"eq.{uid}", "select": "server_uid,id"})
        if not fila:
            return {"servidor": None, "fila": None, "posicao": None}
        alvo = fila[0]
        antes = self._req("GET", "/rest/v1/espera", params={
            "server_uid": f"eq.{alvo['server_uid']}", "id": f"lte.{alvo['id']}", "select": "id"})
        return {"servidor": None, "fila": alvo["server_uid"], "posicao": len(antes)}

    def atualizar_local(self, locate: str) -> None:
        self._req("POST", "/rest/v1/rpc/atualizar_local", json={"p_locate": locate})

    # ------------------------------------------------------------- chat
    def mensagens(self, server_uid: str, depois_de: int = 0) -> list[dict]:
        return self._req("GET", "/rest/v1/servidores_logados", params={
            "server_uid": f"eq.{server_uid}", "id": f"gt.{depois_de}",
            "select": "id,username,mensagem_filtrada,criado_em,bot_id", "order": "id", "limit": "100"})

    def enviar(self, server_uid: str, texto: str, idioma: Optional[str] = None) -> dict:
        return self._rpc("enviar_mensagem", p_server=server_uid, p_texto=texto, p_idioma=idioma)

    # ---------------------------------------------------------- alertas
    def alertas(self) -> list[dict]:
        return self._req("GET", "/rest/v1/alertas_seguranca", params={
            "select": "id,ip,ip_foi_banido,lido,criado_em", "order": "criado_em.desc", "limit": "50"})

    def ver_senha_tentada(self, alerta_id: int) -> str:
        return self._req("POST", "/functions/v1/ver-alerta", json={"alerta_id": alerta_id})["senha_tentada"]

    # ----------------------------------------------------------- tickets
    def receber_tickets(self) -> dict:
        """Presente diário: {"infinito", "ganhou", "tickets", "amanha"}."""
        return self._req("POST", "/rest/v1/rpc/receber_tickets_diarios", json={})

    # --------------------------------------------------------------- ADM
    def adm_painel(self) -> dict:
        return self._req("POST", "/rest/v1/rpc/adm_painel", json={})

    def adm_dar_tickets(self, user_id: str, quantidade: int) -> dict:
        return self._req("POST", "/rest/v1/rpc/adm_dar_tickets", json={"p_user": user_id, "p_qtd": int(quantidade)})

    def adm_banir(self, user_id: str, motivo: str = "") -> None:
        self._req("POST", "/rest/v1/rpc/adm_banir", json={"p_user": user_id, "p_motivo": motivo or None})

    def adm_desbanir(self, user_id: str) -> None:
        self._req("POST", "/rest/v1/rpc/adm_desbanir", json={"p_user": user_id})

    def adm_definir_adm(self, user_id: str, adm: bool) -> None:
        self._req("POST", "/rest/v1/rpc/adm_definir_adm", json={"p_user": user_id, "p_adm": adm})

    def adm_desbloquear_ip(self, ip: str) -> None:
        self._req("POST", "/rest/v1/rpc/adm_desbloquear_ip", json={"p_ip": ip})

    def adm_encerrar_servidor(self, server_uid: str) -> None:
        self._req("POST", "/rest/v1/rpc/adm_encerrar_servidor", json={"p_server": server_uid})

    def adm_sem_chat(self, user_id: str, minutos: int, motivo: str = "") -> dict:
        return self._req("POST", "/rest/v1/rpc/adm_sem_chat",
                         json={"p_user": user_id, "p_minutos": int(minutos), "p_motivo": motivo or None})

    def adm_com_chat(self, user_id: str) -> dict:
        return self._req("POST", "/rest/v1/rpc/adm_com_chat", json={"p_user": user_id})

    def adm_marcar_ip_registrado(self, ip: str) -> None:
        self._req("POST", "/rest/v1/rpc/adm_marcar_ip_registrado", json={"p_ip": ip})
