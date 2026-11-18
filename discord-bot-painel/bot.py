"""
Bot do Discord + Painel web (ler e escrever nos canais pelo navegador).

Roda num único processo: o bot (discord.py) e o servidor web (aiohttp),
pensado para o Render (Web Service). Variáveis de ambiente:

  DISCORD_BOT_TOKEN           (obrigatória) token do bot
  PANEL_PASSWORD              (obrigatória) senha para entrar no painel
  SECRET_KEY                  (obrigatória) chave aleatória para assinar o login
  SUPABASE_URL                (opcional) ex.: https://xxxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY   (opcional) chave service_role (só no servidor!)
  PORT                        (o Render define sozinho)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import quote

import aiohttp
import discord
from aiohttp import web
from discord import app_commands

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("painel")

# ---------------------------------------------------------------- config
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PORT = int(os.environ.get("PORT", "10000"))
PANEL_URL = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{PORT}")

STATIC_DIR = Path(__file__).parent / "static"
SESSION_DAYS = 30
COOKIE_NAME = "painel_sessao"
MAX_UPLOAD = 8 * 1024 * 1024
MAX_LOGIN_FAILS = 5
LOGIN_WINDOW = 15 * 60
SEND_LIMIT = 5  # mensagens...
SEND_WINDOW = 5  # ...a cada 5 segundos por pessoa

# Se a senha mudar no Render, todo mundo é desconectado automaticamente.
PASSWORD_VERSION = hashlib.sha256(PANEL_PASSWORD.encode()).hexdigest()[:12]
NO_MENTIONS = discord.AllowedMentions.none()


# ---------------------------------------------------------------- sessão
def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(name: str) -> str:
    data = {"n": name, "e": int(time.time()) + SESSION_DAYS * 86400, "v": PASSWORD_VERSION}
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def read_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return None
    if data.get("e", 0) < time.time() or data.get("v") != PASSWORD_VERSION:
        return None
    return data


def client_ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote or "?")


def clean_name(raw: str) -> str | None:
    """Nomes de webhook não podem ter certas palavras/caracteres."""
    name = re.sub(r"[@#:`]", "", (raw or "")).strip()
    name = re.sub(r"\s+", " ", name)[:32]
    if len(name) < 2:
        return None
    low = name.lower()
    if "discord" in low or "clyde" in low or low in ("everyone", "here"):
        return None
    return name


login_fails: dict[str, deque] = defaultdict(deque)
send_times: dict[str, deque] = defaultdict(deque)


def _recent(q: deque, window: float) -> deque:
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    return q


# ---------------------------------------------------------------- supabase
async def sb_insert(table: str, row: dict) -> None:
    """Grava um registro no Supabase (se estiver configurado). Nunca derruba o bot."""
    if not (SUPABASE_URL and SUPABASE_KEY and bot.http_session):
        return
    try:
        async with bot.http_session.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            json=row,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "return=minimal",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status >= 300:
                log.warning("Supabase %s: %s %s", table, r.status, await r.text())
    except Exception as exc:  # noqa: BLE001
        log.warning("Supabase indisponível: %s", exc)


# ---------------------------------------------------------------- bot
intents = discord.Intents.default()
intents.message_content = True  # precisa estar ATIVADO no Developer Portal


class PainelBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents, allowed_mentions=NO_MENTIONS)
        self.tree = app_commands.CommandTree(self)
        self.http_session: aiohttp.ClientSession | None = None
        self.runner: web.AppRunner | None = None
        self.webhooks: dict[int, discord.Webhook] = {}
        self.sockets: dict[web.WebSocketResponse, str | None] = {}

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        self.runner = web.AppRunner(build_app())
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", PORT).start()
        log.info("Painel web ouvindo na porta %s", PORT)

    async def sync_commands(self) -> None:
        """Registra os comandos / só se mudaram (evita bloqueio do Discord ao reiniciar)."""
        try:
            local = {(c.name, c.description) for c in self.tree.get_commands()}
            remote = {(c.name, c.description) for c in await self.tree.fetch_commands()}
            if local == remote:
                log.info("Comandos de barra já estão atualizados (%d)", len(local))
                return
            synced = await asyncio.wait_for(self.tree.sync(), timeout=60)
            log.info("%d comandos de barra sincronizados", len(synced))
        except asyncio.TimeoutError:
            log.warning("Discord demorou para registrar os comandos; tento no próximo início")
        except discord.HTTPException as exc:
            log.warning("Falha ao sincronizar comandos: %s", exc)

    async def close(self) -> None:
        for ws in list(self.sockets):
            await ws.close()
        if self.runner:
            await self.runner.cleanup()
        if self.http_session:
            await self.http_session.close()
        await super().close()

    async def broadcast(self, channel_id: int, payload: dict) -> None:
        cid = str(channel_id)
        for ws, sub in list(self.sockets.items()):
            if sub == cid and not ws.closed:
                try:
                    await ws.send_json(payload)
                except (ConnectionError, RuntimeError):
                    self.sockets.pop(ws, None)


bot = PainelBot()


@bot.event
async def on_ready() -> None:
    log.info("Conectado como %s em %d servidor(es)", bot.user, len(bot.guilds))
    if not getattr(bot, "_synced", False):
        bot._synced = True
        asyncio.create_task(bot.sync_commands())


@bot.event
async def on_message(message: discord.Message) -> None:
    await bot.broadcast(message.channel.id, {"type": "message", "message": serialize(message)})


@bot.event
async def on_message_edit(_before: discord.Message, after: discord.Message) -> None:
    await bot.broadcast(after.channel.id, {"type": "edit", "message": serialize(after)})


@bot.event
async def on_raw_message_delete(event: discord.RawMessageDeleteEvent) -> None:
    await bot.broadcast(event.channel_id, {"type": "delete", "id": str(event.message_id)})


@bot.tree.command(name="ping", description="Mostra se o bot está online")
async def cmd_ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)} ms")


@bot.tree.command(name="painel", description="Link do painel para ler e escrever pelo navegador")
async def cmd_painel(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"🌐 Painel: {PANEL_URL}", ephemeral=True)


@bot.tree.command(name="ajuda", description="Lista os comandos do bot")
async def cmd_ajuda(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "**Comandos:**\n`/ping` — status do bot\n`/painel` — link do painel web\n`/ajuda` — esta mensagem",
        ephemeral=True,
    )


# ---------------------------------------------------------------- helpers discord
def serialize(m: discord.Message) -> dict:
    is_normal = m.type in (discord.MessageType.default, discord.MessageType.reply)
    reply = None
    if m.reference and isinstance(m.reference.resolved, discord.Message):
        r = m.reference.resolved
        reply = {"name": r.author.display_name, "content": r.clean_content[:120]}
    return {
        "id": str(m.id),
        "channel_id": str(m.channel.id),
        "author": {
            "id": str(m.author.id),
            "name": m.author.display_name,
            "avatar": m.author.display_avatar.url,
            "bot": m.author.bot,
            "webhook": m.webhook_id is not None,
        },
        "content": m.clean_content if is_normal else (m.system_content or ""),
        "system": not is_normal,
        "ts": m.created_at.isoformat(),
        "edited": m.edited_at is not None,
        "attachments": [
            {
                "url": a.url,
                "name": a.filename,
                "image": (a.content_type or "").startswith("image/"),
            }
            for a in m.attachments
        ],
        "embeds": [
            {
                "title": e.title,
                "description": e.description,
                "url": e.url,
                "image": getattr(e.image, "url", None) or getattr(e.thumbnail, "url", None),
                "color": e.color.value if e.color else None,
            }
            for e in m.embeds
        ],
        "reply": reply,
    }


def readable_channel(channel_id: str) -> discord.TextChannel | None:
    """Só devolve canais de texto que o bot realmente consegue ver e ler."""
    try:
        ch = bot.get_channel(int(channel_id))
    except ValueError:
        return None
    if not isinstance(ch, discord.TextChannel):
        return None
    p = ch.permissions_for(ch.guild.me)
    return ch if (p.view_channel and p.read_message_history) else None


async def get_webhook(ch: discord.TextChannel) -> discord.Webhook | None:
    if ch.id in bot.webhooks:
        return bot.webhooks[ch.id]
    if not ch.permissions_for(ch.guild.me).manage_webhooks:
        return None
    for wh in await ch.webhooks():
        if wh.user and bot.user and wh.user.id == bot.user.id and wh.token:
            bot.webhooks[ch.id] = wh
            return wh
    wh = await ch.create_webhook(name="Painel")
    bot.webhooks[ch.id] = wh
    return wh


# ---------------------------------------------------------------- web
def jerror(status: int, msg: str) -> web.Response:
    return web.json_response({"error": msg}, status=status)


@web.middleware
async def guard(request: web.Request, handler):
    path = request.path
    if request.method == "POST" and request.headers.get("X-Panel") != "1":
        return jerror(403, "Requisição inválida")
    if path.startswith("/api/") or path == "/ws":
        session = read_session(request.cookies.get(COOKIE_NAME))
        if path != "/api/login" and not session:
            return jerror(401, "Faça login")
        request["session"] = session
        if path not in ("/api/login", "/api/me", "/api/logout") and not bot.is_ready():
            return jerror(503, "O bot está conectando, tente em alguns segundos")
    resp = await handler(request)
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


async def page_index(_request: web.Request) -> web.StreamResponse:
    resp = web.FileResponse(STATIC_DIR / "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


async def page_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "discord": bot.is_ready()})


async def api_login(request: web.Request) -> web.Response:
    ip = client_ip(request)
    fails = _recent(login_fails[ip], LOGIN_WINDOW)
    if len(fails) >= MAX_LOGIN_FAILS:
        return jerror(429, "Muitas tentativas. Aguarde 15 minutos.")
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return jerror(400, "Dados inválidos")
    name = clean_name(str(body.get("name", "")))
    password = str(body.get("password", ""))
    if not name:
        return jerror(400, "Nome inválido (2 a 32 letras, sem @ # : e sem a palavra 'discord').")
    ok = hmac.compare_digest(password.encode(), PANEL_PASSWORD.encode())
    asyncio.create_task(sb_insert("panel_logins", {"name": name, "ip": ip, "success": ok}))
    if not ok:
        fails.append(time.time())
        await asyncio.sleep(1)  # atrasa robôs
        return jerror(401, "Senha incorreta")
    login_fails.pop(ip, None)
    resp = web.json_response({"name": name})
    resp.set_cookie(
        COOKIE_NAME,
        make_session(name),
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=PANEL_URL.startswith("https"),
        samesite="Lax",
    )
    return resp


async def api_logout(_request: web.Request) -> web.Response:
    resp = web.json_response({"ok": True})
    resp.del_cookie(COOKIE_NAME)
    return resp


async def api_me(request: web.Request) -> web.Response:
    return web.json_response({"name": request["session"]["n"], "ready": bot.is_ready()})


async def api_guilds(_request: web.Request) -> web.Response:
    out = []
    for g in bot.guilds:
        cats = []
        for cat, chans in g.by_category():
            items = []
            for c in chans:
                if not isinstance(c, discord.TextChannel):
                    continue
                p = c.permissions_for(g.me)
                if not (p.view_channel and p.read_message_history):
                    continue
                items.append({"id": str(c.id), "name": c.name, "topic": c.topic, "can_send": p.send_messages})
            if items:
                cats.append({"name": cat.name if cat else None, "channels": items})
        out.append({"id": str(g.id), "name": g.name, "icon": g.icon.url if g.icon else None, "categories": cats})
    return web.json_response(out)


async def api_messages(request: web.Request) -> web.Response:
    ch = readable_channel(request.match_info["cid"])
    if not ch:
        return jerror(404, "Canal não encontrado ou sem acesso")
    before = request.query.get("before")
    kwargs = {"limit": 50}
    if before and before.isdigit():
        kwargs["before"] = discord.Object(id=int(before))
    try:
        msgs = [m async for m in ch.history(**kwargs)]
    except discord.Forbidden:
        return jerror(403, "O bot não pode ler este canal")
    msgs.reverse()
    return web.json_response([serialize(m) for m in msgs])


async def api_send(request: web.Request) -> web.Response:
    name = request["session"]["n"]
    ch = readable_channel(request.match_info["cid"])
    if not ch:
        return jerror(404, "Canal não encontrado ou sem acesso")
    if not ch.permissions_for(ch.guild.me).send_messages:
        return jerror(403, "O bot não pode escrever neste canal")
    if len(_recent(send_times[name], SEND_WINDOW)) >= SEND_LIMIT:
        return jerror(429, "Calma! Espere alguns segundos.")

    content, reply_to, file_data, file_name = "", None, None, None
    reader = await request.multipart()
    async for part in reader:
        if part.name == "content":
            content = (await part.text()).strip()
        elif part.name == "reply_to":
            reply_to = (await part.text()).strip() or None
        elif part.name == "file" and part.filename:
            file_name = part.filename[:100]
            file_data = await part.read(decode=False)
            if len(file_data) > MAX_UPLOAD:
                return jerror(413, "Arquivo maior que 8 MB")
    if not content and not file_data:
        return jerror(400, "Mensagem vazia")

    reply_msg = None
    if reply_to and reply_to.isdigit():
        try:
            reply_msg = await ch.fetch_message(int(reply_to))
        except discord.HTTPException:
            reply_msg = None

    def files() -> dict:
        if not file_data:
            return {}
        return {"file": discord.File(io.BytesIO(file_data), filename=file_name)}

    send_times[name].append(time.time())
    sent: discord.Message | None = None
    try:
        wh = await get_webhook(ch)
    except discord.HTTPException:
        wh = None

    if wh:
        text = content
        if reply_msg:
            quoted = reply_msg.clean_content.replace("\n", " ")[:80]
            text = f"> **{reply_msg.author.display_name}:** {quoted}\n{content}"
        if len(text) > 2000:
            return jerror(400, "Mensagem passou de 2000 caracteres")
        for attempt in range(2):
            try:
                sent = await wh.send(
                    content=text or None,
                    username=f"{name} (via painel)",
                    avatar_url=f"https://api.dicebear.com/9.x/initials/png?seed={quote(name)}",
                    **files(),
                    allowed_mentions=NO_MENTIONS,
                    wait=True,
                )
                break
            except discord.NotFound:  # webhook foi apagado no Discord
                bot.webhooks.pop(ch.id, None)
                wh = await get_webhook(ch)
                if not wh or attempt:
                    break
    if sent is None:
        text = f"**{name}:** {content}" if content else f"**{name}** enviou um arquivo"
        if len(text) > 2000:
            return jerror(400, "Mensagem passou de 2000 caracteres")
        try:
            sent = await ch.send(
                content=text,
                **files(),
                allowed_mentions=NO_MENTIONS,
                reference=reply_msg.to_reference(fail_if_not_exists=False) if reply_msg else None,
            )
        except discord.HTTPException as exc:
            return jerror(502, f"O Discord recusou a mensagem: {exc.text or exc}")

    asyncio.create_task(
        sb_insert(
            "panel_messages",
            {
                "name": name,
                "guild_id": str(ch.guild.id),
                "channel_id": str(ch.id),
                "discord_message_id": str(sent.id),
                "content": content[:2000],
                "has_file": bool(file_data),
            },
        )
    )
    return web.json_response(serialize(sent))


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    bot.sockets[ws] = None
    try:
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "subscribe":
                cid = str(data.get("channel_id", ""))
                bot.sockets[ws] = cid if readable_channel(cid) else None
    finally:
        bot.sockets.pop(ws, None)
    return ws


def build_app() -> web.Application:
    app = web.Application(middlewares=[guard], client_max_size=MAX_UPLOAD + 1024 * 1024)
    app.router.add_get("/", page_index)
    app.router.add_get("/health", page_health)
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/guilds", api_guilds)
    app.router.add_get("/api/channels/{cid}/messages", api_messages)
    app.router.add_post("/api/channels/{cid}/messages", api_send)
    app.router.add_get("/ws", ws_handler)
    return app


# ---------------------------------------------------------------- main
def main() -> None:
    missing = [k for k, v in {
        "DISCORD_BOT_TOKEN": DISCORD_TOKEN,
        "PANEL_PASSWORD": PANEL_PASSWORD,
        "SECRET_KEY": SECRET_KEY,
    }.items() if not v]
    if missing:
        raise SystemExit(f"Faltam variáveis de ambiente: {', '.join(missing)}")
    try:
        bot.run(DISCORD_TOKEN, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "Ative o 'MESSAGE CONTENT INTENT' em discord.com/developers → seu app → Bot → Privileged Gateway Intents."
        ) from None


if __name__ == "__main__":
    main()
