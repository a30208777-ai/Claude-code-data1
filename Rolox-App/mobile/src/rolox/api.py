"""Cliente do Supabase para o Rolox Mobile.

O celular acessa direto as bases de dados (REST do Supabase) e as regras RLS
garantem que cada jogador só lê e altera o que pode. O login passa pela Edge
Function `login-protegido`, que aplica a regra das 3 tentativas.

Só usa `httpx` (já vem com o Flet), para funcionar no APK sem dependências nativas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from . import config

USERNAME_VALIDO = re.compile(r"^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$")

MENSAGENS = {
    "credenciais_invalidas": "Usuário ou senha incorretos.",
    "ip_bloqueado": "Este aparelho/rede foi bloqueado após 3 senhas erradas.",
    "conta_banida": "Esta conta foi banida por um moderador.",
    "confirme_por_email": "Muitas tentativas. Enviamos um e-mail para você redefinir a senha.",
    "dados_invalidos": "Preencha usuário e senha.",
    "username_invalido": "O usuário deve ter 3 a 32 letras minúsculas, números ou hífen "
                         "(sem hífen no começo ou no fim).",
    "senha_curta": "A senha precisa ter pelo menos 8 caracteres.",
    "email_invalido": "E-mail inválido.",
    "username_em_uso": "Esse nome de usuário já está em uso.",
    "sessao_expirada": "Sua sessão expirou. Entre novamente.",
    "sem_conexao": "Sem conexão com o servidor. Verifique sua internet.",
    "NOT_FOUND": "O servidor do Rolox ainda não foi configurado no Supabase "
                 "(função de login não encontrada).",
    "PGRST205": "O banco do Rolox ainda não foi configurado no Supabase (tabela não encontrada).",
    # resultados das RPCs
    "servidor_inexistente": "Esse servidor não existe mais.",
    "use_servidor_hack": "Você marcou hack/mod neste jogo. Entre em um servidor de hack.",
    "servidor_so_para_hack": "Servidor exclusivo para quem usa hack/mod neste jogo.",
    "fora_do_servidor": "Você não está neste servidor.",
    "muito_rapido": "Calma! Espere um segundo entre as mensagens.",
    "tamanho_invalido": "A mensagem deve ter entre 1 e 500 caracteres.",
    "alerta_nao_encontrado": "Alerta não encontrado.",
}


class ErroRolox(Exception):
    def __init__(self, codigo: str, detalhes: Optional[dict] = None):
        self.codigo = codigo
        self.detalhes = detalhes or {}
        super().__init__(codigo)

    @property
    def mensagem(self) -> str:
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


@dataclass
class RoloxAPI:
    url: str = config.SUPABASE_URL
    chave: str = config.SUPABASE_CHAVE
    transport: Optional[httpx.AsyncBaseTransport] = None
    sessao: Optional[Sessao] = None
    _cliente: Optional[httpx.AsyncClient] = field(default=None, repr=False)

    # ------------------------------------------------------------------ base
    @property
    def cliente(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                base_url=self.url.rstrip("/"), timeout=15, transport=self.transport
            )
        return self._cliente

    async def fechar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    @property
    def user_id(self) -> str:
        if not self.sessao:
            raise ErroRolox("sessao_expirada")
        return self.sessao.user_id

    def _cabecalhos(self, autenticado: bool) -> dict[str, str]:
        h = {"apikey": self.chave, "Content-Type": "application/json"}
        if autenticado:
            if not self.sessao:
                raise ErroRolox("sessao_expirada")
            h["Authorization"] = f"Bearer {self.sessao.access_token}"
        return h

    async def _req(
        self,
        metodo: str,
        caminho: str,
        *,
        json: Any = None,
        params: Optional[dict] = None,
        autenticado: bool = True,
        prefer: Optional[str] = None,
        renovar_se_expirado: bool = True,
    ) -> Any:
        cab = self._cabecalhos(autenticado)
        if prefer:
            cab["Prefer"] = prefer
        try:
            r = await self.cliente.request(metodo, caminho, json=json, params=params, headers=cab)
        except httpx.TransportError as e:
            raise ErroRolox("sem_conexao") from e

        if r.status_code == 401 and autenticado and renovar_se_expirado and self.sessao:
            await self.renovar()
            return await self._req(
                metodo, caminho, json=json, params=params,
                autenticado=True, prefer=prefer, renovar_se_expirado=False,
            )

        if r.status_code >= 400:
            try:
                corpo = r.json()
            except ValueError:
                corpo = {}
            codigo = (
                corpo.get("erro")
                or corpo.get("error_code")
                or corpo.get("code")
                or corpo.get("error")
                or f"http_{r.status_code}"
            )
            raise ErroRolox(str(codigo), corpo)

        if not r.content:
            return None
        return r.json()

    @staticmethod
    def _resultado_rpc(dados: dict) -> dict:
        """As RPCs devolvem {"resultado": ...}; códigos de bloqueio viram ErroRolox."""
        ok = {"entrou", "ja_esta", "fila", "saiu", "enviada"}
        if dados.get("resultado") not in ok:
            raise ErroRolox(str(dados.get("resultado")), dados)
        return dados

    # ----------------------------------------------------------------- conta
    async def login(self, username: str, senha: str) -> Sessao:
        username = username.strip().lower()
        if not username or not senha:
            raise ErroRolox("dados_invalidos")
        dados = await self._req(
            "POST", "/functions/v1/login-protegido",
            json={"username": username, "senha": senha},
            autenticado=False,
        )
        self.sessao = Sessao(dados["access_token"], dados["refresh_token"], dados["user_id"])
        return self.sessao

    async def cadastrar(self, email: str, username: str, senha: str,
                        aceitou_localizacao: bool) -> dict:
        username = username.strip().lower()
        email = email.strip()
        if not USERNAME_VALIDO.match(username):
            raise ErroRolox("username_invalido")
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ErroRolox("email_invalido")
        if len(senha) < 8:
            raise ErroRolox("senha_curta")
        try:
            return await self._req(
                "POST", "/auth/v1/signup",
                json={
                    "email": email,
                    "password": senha,
                    "data": {"username": username, "aceitou_localizacao": aceitou_localizacao},
                },
                autenticado=False,
            )
        except ErroRolox as e:
            # username duplicado estoura a constraint unique no trigger
            if e.codigo in ("unexpected_failure", "http_500") or "Database error" in str(e.detalhes):
                raise ErroRolox("username_em_uso", e.detalhes) from e
            raise

    async def renovar(self, refresh_token: Optional[str] = None) -> Sessao:
        token = refresh_token or (self.sessao.refresh_token if self.sessao else None)
        if not token:
            raise ErroRolox("sessao_expirada")
        try:
            dados = await self._req(
                "POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
                json={"refresh_token": token}, autenticado=False,
            )
        except ErroRolox as e:
            if e.codigo == "sem_conexao":
                raise
            self.sessao = None
            raise ErroRolox("sessao_expirada") from e
        self.sessao = Sessao(dados["access_token"], dados["refresh_token"], dados["user"]["id"])
        return self.sessao

    async def sair_da_conta(self) -> None:
        if self.sessao:
            try:
                await self._req("POST", "/auth/v1/logout", renovar_se_expirado=False)
            except ErroRolox:
                pass
        self.sessao = None

    # ---------------------------------------------------------------- perfil
    async def meu_perfil(self) -> dict:
        linhas = await self._req(
            "GET", "/rest/v1/perfis",
            params={"id": f"eq.{self.user_id}",
                    "select": "id,username,idioma,jogo_mod,aceitou_localizacao,banido"},
        )
        if not linhas:
            raise ErroRolox("perfil_nao_encontrado")
        return linhas[0]

    async def atualizar_perfil(self, **campos: Any) -> dict:
        permitidos = {"idioma", "jogo_mod", "aceitou_localizacao"}
        invalidos = set(campos) - permitidos
        if invalidos:
            raise ValueError(f"campos não editáveis: {sorted(invalidos)}")
        linhas = await self._req(
            "PATCH", "/rest/v1/perfis", params={"id": f"eq.{self.user_id}"},
            json=campos, prefer="return=representation",
        )
        return linhas[0] if linhas else {}

    async def jogos(self) -> list[dict]:
        return await self._req(
            "GET", "/rest/v1/jogos", params={"select": "gameid,nome", "order": "nome"},
            autenticado=self.sessao is not None,
        )

    # ------------------------------------------------------------ servidores
    async def servidores(self) -> list[dict]:
        linhas = await self._req(
            "GET", "/rest/v1/servidores_ativos",
            params={
                "select": "server_uid,gameid,host_id,capacidade,is_hack_server,status,"
                          "users_dos_servidores(count)",
                "status": "neq.encerrando",
                "order": "criado_em.desc",
                "limit": "100",
            },
        )
        for s in linhas:
            contagem = s.pop("users_dos_servidores", None) or [{"count": 0}]
            s["jogadores"] = contagem[0].get("count", 0)
        return linhas

    async def criar_servidor(self, gameid: str, capacidade: int, hack: bool) -> dict:
        if not 1 <= capacidade <= 100:
            raise ValueError("capacidade deve ficar entre 1 e 100")
        linhas = await self._req(
            "POST", "/rest/v1/servidores_ativos",
            json={"gameid": gameid, "host_id": self.user_id,
                  "capacidade": capacidade, "is_hack_server": hack},
            prefer="return=representation",
        )
        return linhas[0]

    async def heartbeat(self, server_uid: str) -> None:
        from datetime import datetime, timezone
        await self._req(
            "PATCH", "/rest/v1/servidores_ativos",
            params={"server_uid": f"eq.{server_uid}", "host_id": f"eq.{self.user_id}"},
            json={"ultimo_heartbeat": datetime.now(timezone.utc).isoformat()},
        )

    async def entrar(self, server_uid: str) -> dict:
        return self._resultado_rpc(
            await self._req("POST", "/rest/v1/rpc/entrar_servidor", json={"p_server": server_uid})
        )

    async def sair(self, server_uid: str) -> dict:
        return self._resultado_rpc(
            await self._req("POST", "/rest/v1/rpc/sair_servidor", json={"p_server": server_uid})
        )

    async def onde_estou(self) -> dict:
        """{"servidor": uid|None, "fila": uid|None, "posicao": int|None}"""
        uid = self.user_id
        dentro = await self._req(
            "GET", "/rest/v1/users_dos_servidores",
            params={"user_id": f"eq.{uid}", "select": "server_uid"},
        )
        if dentro:
            return {"servidor": dentro[0]["server_uid"], "fila": None, "posicao": None}
        fila = await self._req(
            "GET", "/rest/v1/espera",
            params={"user_id": f"eq.{uid}", "select": "server_uid,id"},
        )
        if not fila:
            return {"servidor": None, "fila": None, "posicao": None}
        alvo = fila[0]
        antes = await self._req(
            "GET", "/rest/v1/espera",
            params={"server_uid": f"eq.{alvo['server_uid']}", "id": f"lte.{alvo['id']}",
                    "select": "id"},
        )
        return {"servidor": None, "fila": alvo["server_uid"], "posicao": len(antes)}

    async def atualizar_local(self, locate: str) -> None:
        await self._req("POST", "/rest/v1/rpc/atualizar_local", json={"p_locate": locate})

    # ------------------------------------------------------------------ chat
    async def mensagens(self, server_uid: str, depois_de: int = 0) -> list[dict]:
        return await self._req(
            "GET", "/rest/v1/servidores_logados",
            params={
                "server_uid": f"eq.{server_uid}",
                "id": f"gt.{depois_de}",
                "select": "id,username,mensagem_filtrada,criado_em",
                "order": "id",
                "limit": "100",
            },
        )

    async def enviar(self, server_uid: str, texto: str, idioma: Optional[str] = None) -> dict:
        return self._resultado_rpc(
            await self._req(
                "POST", "/rest/v1/rpc/enviar_mensagem",
                json={"p_server": server_uid, "p_texto": texto, "p_idioma": idioma},
            )
        )

    # --------------------------------------------------------------- alertas
    async def alertas(self) -> list[dict]:
        return await self._req(
            "GET", "/rest/v1/alertas_seguranca",
            params={"select": "id,ip,ip_foi_banido,lido,criado_em",
                    "order": "criado_em.desc", "limit": "50"},
        )

    async def ver_senha_tentada(self, alerta_id: int) -> str:
        dados = await self._req("POST", "/functions/v1/ver-alerta", json={"alerta_id": alerta_id})
        return dados["senha_tentada"]
