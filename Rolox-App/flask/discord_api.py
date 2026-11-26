"""🔗 VISTA ↔ Discord (servidor VISTA): login com o Discord, cargos, castigo, ban e eventos.

As chaves ficam SÓ nas variáveis do Render (nunca no Git):
  DISCORD_BOT_TOKEN      token do VISTA BOT
  DISCORD_CLIENT_SECRET  Client Secret (OAuth2) do VISTA BOT
"""
import os
import secrets
from urllib.parse import urlencode

import requests

API = "https://discord.com/api/v10"
CLIENT_ID = "1575526403322019927"
SERVIDOR = "1569008166648291439"                      # servidor "VISTA"
REDIRECT = os.environ.get("DISCORD_REDIRECT", "https://rolox-gj2i.onrender.com/discord/callback")
# cargos que JÁ existem no servidor VISTA (se algum sumir, o bot cria com este nome)
CARGOS = {"jogador": "Membro", "adm": "📕 ADMS 📕", "subdono": "💎SUB-DONO💎", "dono": "👑💎DONO💎👑"}


class ErroDiscord(Exception):
    pass


def _token() -> str:
    return os.environ.get("DISCORD_BOT_TOKEN", "")


def configurado() -> dict:
    return {"bot": bool(_token()), "login": bool(os.environ.get("DISCORD_CLIENT_SECRET"))}


def link_login(estado: str) -> str:
    return "https://discord.com/oauth2/authorize?" + urlencode(
        {"client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT, "scope": "identify", "state": estado})


def novo_estado() -> str:
    return secrets.token_urlsafe(24)


def usuario_do_codigo(codigo: str, http=requests) -> dict:
    """Troca o code do OAuth pelo usuário do Discord ({id, username, global_name})."""
    segredo = os.environ.get("DISCORD_CLIENT_SECRET", "")
    if not segredo:
        raise ErroDiscord("O login com o Discord ainda não foi configurado (falta DISCORD_CLIENT_SECRET no Render).")
    r = http.post(f"{API}/oauth2/token", timeout=15, data={
        "client_id": CLIENT_ID, "client_secret": segredo, "grant_type": "authorization_code",
        "code": codigo, "redirect_uri": REDIRECT}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code != 200:
        raise ErroDiscord("O Discord não aceitou o login. Tente de novo.")
    acesso = r.json().get("access_token")
    u = http.get(f"{API}/users/@me", headers={"Authorization": f"Bearer {acesso}"}, timeout=15)
    if u.status_code != 200:
        raise ErroDiscord("Não deu para ler sua conta do Discord.")
    return u.json()


def _bot(metodo: str, caminho: str, http=requests, **kw):
    if not _token():
        raise ErroDiscord("Bot do Discord não configurado (falta DISCORD_BOT_TOKEN no Render).")
    cab = {"Authorization": f"Bot {_token()}", "Content-Type": "application/json"}
    if kw.pop("motivo", None):
        cab["X-Audit-Log-Reason"] = "VISTA (site)"
    r = http.request(metodo, f"{API}{caminho}", headers=cab, timeout=15, **kw)
    if r.status_code >= 400:
        raise ErroDiscord(f"Discord respondeu {r.status_code}")
    return r.json() if r.content else None


def _id_cargo(nome: str, http=requests) -> str:
    for c in _bot("GET", f"/guilds/{SERVIDOR}/roles", http) or []:
        if c.get("name") == nome:
            return c["id"]
    return _bot("POST", f"/guilds/{SERVIDOR}/roles", http, json={"name": nome, "mentionable": False})["id"]


def dar_cargo(discord_id: str, cargo: str | None, http=requests) -> bool:
    """Dá 🎮 Jogador VISTA + o cargo do site (ADM/Sub dono/Dono). False se a pessoa não está no servidor."""
    try:
        _bot("GET", f"/guilds/{SERVIDOR}/members/{discord_id}", http)
    except ErroDiscord:
        return False
    for chave in ["jogador"] + ([cargo] if cargo in CARGOS else []):
        _bot("PUT", f"/guilds/{SERVIDOR}/members/{discord_id}/roles/{_id_cargo(CARGOS[chave], http)}", http, motivo=True)
    return True


def castigo(discord_id: str, minutos: int | None, http=requests):
    """Castigo (timeout) no Discord. minutos=None tira o castigo. Máximo do Discord: 28 dias."""
    import datetime as dt
    ate = None if not minutos else (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=min(minutos, 40320))).isoformat()
    _bot("PATCH", f"/guilds/{SERVIDOR}/members/{discord_id}", http, json={"communication_disabled_until": ate}, motivo=True)


def banir(discord_id: str, sim: bool = True, http=requests):
    if sim:
        _bot("PUT", f"/guilds/{SERVIDOR}/bans/{discord_id}", http, json={"delete_message_seconds": 0}, motivo=True)
    else:
        _bot("DELETE", f"/guilds/{SERVIDOR}/bans/{discord_id}", http, motivo=True)


def criar_evento(nome: str, inicio_iso: str, fim_iso: str, link: str, http=requests) -> dict:
    """Evento agendado no servidor do Discord (local = link do evento no VISTA)."""
    return _bot("POST", f"/guilds/{SERVIDOR}/scheduled-events", http, json={
        "name": nome[:100], "privacy_level": 2, "entity_type": 3, "scheduled_start_time": inicio_iso,
        "scheduled_end_time": fim_iso, "entity_metadata": {"location": link[:100]},
        "description": f"Evento do VISTA! Entre pelo link: {link}"[:1000]}, motivo=True)
