"""Bot do ROLOX no Discord.

- Respostas automáticas do arquivo Fases/ROLOX_DISCORD.md (!fases, !tickets, ... e palavras-chave)
- Moderação, registrada nos webhooks:
    !ban @membro [motivo]               -> webhook de BANIMENTOS
    !desban <id> [motivo]               -> webhook de BANIMENTOS
    !semchat @membro <tempo> [motivo]   -> webhook de PUNIÇÕES  (castigo do Discord; tempo: 10m, 2h, 1d, até 28d)
    !comchat @membro                    -> webhook de PUNIÇÕES
    !aviso @membro <motivo>             -> webhook de PUNIÇÕES
  Banimentos e castigos feitos pelo menu do próprio Discord também são registrados.

Configuração em ~/.rolox.env:
    DISCORD_TOKEN=...
    ROLOX_WEBHOOK_BANIMENTOS=https://discord.com/api/webhooks/...
    ROLOX_WEBHOOK_PUNICOES=https://discord.com/api/webhooks/...
"""

from __future__ import annotations

import os
import re
import time
from datetime import timedelta
from pathlib import Path

import discord
from discord.ext import commands

from discord_log import carregar_env, configurado, registrar
from respostas import Respostas

PASTA = Path(__file__).resolve().parent
TEMPO_MAXIMO = timedelta(days=28)          # limite do castigo do Discord
ESPERA_PALAVRAS = 90                       # segundos entre respostas automáticas iguais no mesmo canal
ONDE = "Discord"


def ler_tempo(texto: str) -> timedelta | None:
    """'10m' -> 10 min, '2h', '1d', '30' (minutos). None se inválido ou maior que 28 dias."""
    m = re.fullmatch(r"(\d{1,5})\s*(m|min|h|d)?", (texto or "").strip().lower())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2) or "m"
    t = {"m": timedelta(minutes=n), "min": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[u]
    return t if timedelta(0) < t <= TEMPO_MAXIMO else None


def minutos(t: timedelta) -> int:
    return max(1, int(t.total_seconds() // 60))


class RoloxBot(commands.Bot):
    def __init__(self, respostas: Respostas):
        intents = discord.Intents.default()
        intents.message_content = True      # ler "!fases" e as palavras-chave
        intents.members = True              # ver castigos (sem chat)
        intents.moderation = True           # ver banimentos
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.respostas = respostas
        self.ultimas: dict[tuple, float] = {}
        self.feitos_por_comando: dict[tuple, float] = {}   # evita registrar duas vezes

    def marcar(self, guild_id: int, user_id: int, acao: str) -> None:
        self.feitos_por_comando[(guild_id, user_id, acao)] = time.monotonic()

    def ja_registrado(self, guild_id: int, user_id: int, acao: str) -> bool:
        t = self.feitos_por_comando.pop((guild_id, user_id, acao), None)
        return t is not None and time.monotonic() - t < 30

    async def on_ready(self):
        cfg = configurado()
        print(f"ROLOX bot online como {self.user} · {len(self.respostas.lista)} respostas · "
              f"webhook banimentos={'ok' if cfg['banimentos'] else 'FALTA'} punições={'ok' if cfg['punicoes'] else 'FALTA'}")

    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.content:
            return
        texto = msg.content.strip()
        if texto.startswith("!"):
            r = self.respostas.por_comando(texto)
            if r:
                await msg.reply(r.texto, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
                return
            await self.process_commands(msg)
            return
        # palavras-chave: só quando é uma pergunta ou o bot foi marcado
        if not (texto.endswith("?") or (self.user and self.user in msg.mentions)):
            return
        r = self.respostas.por_palavras(texto)
        if not r:
            return
        chave = (msg.channel.id, r.titulo)
        agora = time.monotonic()
        if agora - self.ultimas.get(chave, 0) < ESPERA_PALAVRAS:
            return
        self.ultimas[chave] = agora
        await msg.reply(r.texto, mention_author=False, allowed_mentions=discord.AllowedMentions.none())

    # ------------------------------------------- moderação feita pelo menu
    async def _do_registro(self, guild: discord.Guild, alvo_id: int, acao: discord.AuditLogAction):
        try:
            async for e in guild.audit_logs(limit=6, action=acao):
                if e.target and e.target.id == alvo_id:
                    return (str(e.user) if e.user else "?"), (e.reason or "")
        except (discord.Forbidden, discord.HTTPException):
            pass
        return "?", ""

    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if self.ja_registrado(guild.id, user.id, "ban"):
            return
        por, motivo = await self._do_registro(guild, user.id, discord.AuditLogAction.ban)
        await registrar("ban", f"{user} ({user.id})", motivo, por, ONDE)

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if self.ja_registrado(guild.id, user.id, "desban"):
            return
        por, motivo = await self._do_registro(guild, user.id, discord.AuditLogAction.unban)
        await registrar("desban", f"{user} ({user.id})", motivo, por, ONDE)

    async def on_member_update(self, antes: discord.Member, depois: discord.Member):
        if antes.timed_out_until == depois.timed_out_until:
            return
        g = depois.guild
        if depois.is_timed_out():
            if self.ja_registrado(g.id, depois.id, "sem_chat"):
                return
            por, motivo = await self._do_registro(g, depois.id, discord.AuditLogAction.member_update)
            dur = depois.timed_out_until - discord.utils.utcnow()
            await registrar("sem_chat", f"{depois} ({depois.id})", motivo, por, ONDE, minutos(dur))
        else:
            if self.ja_registrado(g.id, depois.id, "com_chat"):
                return
            por, motivo = await self._do_registro(g, depois.id, discord.AuditLogAction.member_update)
            await registrar("com_chat", f"{depois} ({depois.id})", motivo, por, ONDE)


def criar_bot(caminho_respostas: str | Path) -> RoloxBot:
    bot = RoloxBot(Respostas(caminho_respostas))

    async def responder(ctx, texto: str):
        await ctx.reply(texto, mention_author=False, allowed_mentions=discord.AllowedMentions.none())

    @bot.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(ctx, membro: discord.Member, *, motivo: str = ""):
        if membro == ctx.author or membro.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await responder(ctx, "❌ Você não pode banir esse membro.")
        bot.marcar(ctx.guild.id, membro.id, "ban")
        await membro.ban(reason=f"{motivo or 'sem motivo'} (por {ctx.author})", delete_message_seconds=0)
        ok = await registrar("ban", f"{membro} ({membro.id})", motivo, str(ctx.author), ONDE)
        await responder(ctx, f"🔨 {membro} foi banido." + ("" if ok else " (⚠️ webhook de banimentos não configurado)"))

    @bot.command(name="desban")
    @commands.has_permissions(ban_members=True)
    async def desban(ctx, usuario_id: int, *, motivo: str = ""):
        usuario = await bot.fetch_user(usuario_id)
        bot.marcar(ctx.guild.id, usuario.id, "desban")
        await ctx.guild.unban(usuario, reason=f"{motivo or 'sem motivo'} (por {ctx.author})")
        ok = await registrar("desban", f"{usuario} ({usuario.id})", motivo, str(ctx.author), ONDE)
        await responder(ctx, f"✅ {usuario} foi desbanido." + ("" if ok else " (⚠️ webhook não configurado)"))

    @bot.command(name="semchat")
    @commands.has_permissions(moderate_members=True)
    async def semchat(ctx, membro: discord.Member, tempo: str, *, motivo: str = ""):
        dur = ler_tempo(tempo)
        if not dur:
            return await responder(ctx, "❌ Tempo inválido. Use, por exemplo: `10m`, `2h`, `1d` (máximo 28d).")
        bot.marcar(ctx.guild.id, membro.id, "sem_chat")
        await membro.timeout(dur, reason=f"{motivo or 'sem motivo'} (por {ctx.author})")
        ok = await registrar("sem_chat", f"{membro} ({membro.id})", motivo, str(ctx.author), ONDE, minutos(dur))
        await responder(ctx, f"🔇 {membro} está sem chat por {tempo}." + ("" if ok else " (⚠️ webhook de punições não configurado)"))

    @bot.command(name="comchat")
    @commands.has_permissions(moderate_members=True)
    async def comchat(ctx, membro: discord.Member, *, motivo: str = ""):
        bot.marcar(ctx.guild.id, membro.id, "com_chat")
        await membro.timeout(None, reason=f"{motivo or 'chat liberado'} (por {ctx.author})")
        ok = await registrar("com_chat", f"{membro} ({membro.id})", motivo, str(ctx.author), ONDE)
        await responder(ctx, f"💬 {membro} pode falar de novo." + ("" if ok else " (⚠️ webhook não configurado)"))

    @bot.command(name="aviso")
    @commands.has_permissions(moderate_members=True)
    async def aviso(ctx, membro: discord.Member, *, motivo: str):
        ok = await registrar("aviso", f"{membro} ({membro.id})", motivo, str(ctx.author), ONDE)
        await responder(ctx, f"⚠️ Aviso registrado para {membro}." + ("" if ok else " (⚠️ webhook não configurado)"))

    @bot.command(name="recarregar")
    @commands.has_permissions(manage_guild=True)
    async def recarregar(ctx):
        await responder(ctx, f"🔄 {bot.respostas.recarregar()} respostas carregadas.")

    @bot.command(name="ajuda")
    async def ajuda(ctx):
        cmds = " ".join(f"`{c}`" for c in bot.respostas.comandos())
        await responder(ctx, f"📖 Comandos: {cmds}\n🛡️ Moderação: `!ban` `!desban` `!semchat` `!comchat` `!aviso`")

    @bot.event
    async def on_command_error(ctx, erro):
        if isinstance(erro, commands.MissingPermissions):
            await responder(ctx, "❌ Você não tem permissão para isso.")
        elif isinstance(erro, (commands.MissingRequiredArgument, commands.BadArgument, commands.MemberNotFound)):
            await responder(ctx, "❌ Uso: `!ban @membro motivo` · `!semchat @membro 10m motivo` · `!comchat @membro` · `!aviso @membro motivo` · `!desban ID`")
        elif isinstance(erro, commands.CommandNotFound):
            pass
        elif isinstance(getattr(erro, "original", None), discord.Forbidden):
            await responder(ctx, "❌ O bot não tem permissão (o cargo do bot precisa ficar acima do membro).")
        else:
            print("erro no comando:", repr(erro))

    return bot


def main() -> None:
    carregar_env()
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("Falta o DISCORD_TOKEN no ~/.rolox.env (veja o README).")
    respostas = os.environ.get("ROLOX_RESPOSTAS", str(PASTA.parent / "Fases" / "ROLOX_DISCORD.md"))
    criar_bot(respostas).run(token)


if __name__ == "__main__":
    main()
