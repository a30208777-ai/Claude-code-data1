"""Testes do bot e dos registros nos webhooks (sem internet e sem Discord de verdade).

Rodar: cd Rolox-Discord && python -m pytest -q
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

PASTA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA))

import discord_log  # noqa: E402
from respostas import Respostas, normalizar  # noqa: E402

URL_B = "https://discord.com/api/webhooks/111/aaa-B"
URL_P = "https://discord.com/api/webhooks/222/bbb-P"


@pytest.fixture
def webhooks(monkeypatch):
    monkeypatch.setenv("ROLOX_WEBHOOK_BANIMENTOS", URL_B)
    monkeypatch.setenv("ROLOX_WEBHOOK_PUNICOES", URL_P)


def capturar(status=204):
    enviados = []

    def h(req):
        enviados.append((str(req.url), json.loads(req.content)))
        return httpx.Response(status)
    return enviados, httpx.MockTransport(h)


# ------------------------------------------------------------ webhooks
def test_banimentos_e_punicoes_vao_para_o_webhook_certo(webhooks):
    enviados, t = capturar()
    assert asyncio.run(discord_log.registrar("ban", "bob", "xingou", "admtest (ADM)", transport=t))
    assert asyncio.run(discord_log.registrar("ip_bloqueado", "IP 1.2.3.4", transport=t))
    assert asyncio.run(discord_log.registrar("sem_chat", "bob", "spam", "admtest (ADM)", duracao_min=60, transport=t))
    assert asyncio.run(discord_log.registrar("com_chat", "bob", transport=t))
    assert [u for u, _ in enviados] == [URL_B, URL_B, URL_P, URL_P]
    titulos = [c["embeds"][0]["title"] for _, c in enviados]
    assert titulos == ["🔨 Banimento", "🛡️ IP bloqueado", "🔇 Sem chat", "💬 Chat liberado"]


def test_mensagem_tem_campos_e_nao_marca_ninguem():
    agora = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    m = discord_log.montar_mensagem("sem_chat", "bob", "@everyone spam", "admtest (ADM)", "Jogo ROLOX", 1440, agora)
    assert m["allowed_mentions"] == {"parse": []}
    campos = {c["name"]: c["value"] for c in m["embeds"][0]["fields"]}
    assert campos["Jogador"] == "bob" and campos["Por"] == "admtest (ADM)" and campos["Duração"] == "1 dia"
    fim = int((agora + timedelta(days=1)).timestamp())
    assert campos["Até"] == f"<t:{fim}:f> (<t:{fim}:R>)"
    assert campos["Motivo"] == "@everyone spam"           # aparece, mas não marca (allowed_mentions)
    assert discord_log.montar_mensagem("ban", "x", onde="Discord")["embeds"][0]["fields"][0]["name"] == "Membro"


def test_textos_longos_sao_cortados():
    m = discord_log.montar_mensagem("ban", "a" * 500, "m" * 5000)
    campos = {c["name"]: c["value"] for c in m["embeds"][0]["fields"]}
    assert len(campos["Jogador"]) == 256 and len(campos["Motivo"]) == 1000


def test_sem_webhook_ou_link_estranho_nao_envia(monkeypatch):
    monkeypatch.delenv("ROLOX_WEBHOOK_BANIMENTOS", raising=False)
    monkeypatch.setenv("ROLOX_WEBHOOK_PUNICOES", "https://site-falso.com/api/webhooks/1/x")
    enviados, t = capturar()
    assert asyncio.run(discord_log.registrar("ban", "bob", transport=t)) is False
    assert asyncio.run(discord_log.registrar("sem_chat", "bob", transport=t)) is False
    assert enviados == [] and discord_log.configurado() == {"banimentos": False, "punicoes": False}


def test_discord_fora_do_ar_nao_quebra(webhooks):
    def h(req):
        raise httpx.ConnectError("sem rede", request=req)
    assert asyncio.run(discord_log.registrar("ban", "bob", transport=httpx.MockTransport(h))) is False


def test_limite_do_discord_tenta_de_novo(webhooks, monkeypatch):
    esperas = []

    async def sem_esperar(segundos):
        esperas.append(segundos)
    monkeypatch.setattr(discord_log.asyncio, "sleep", sem_esperar)
    respostas = [httpx.Response(429, json={"retry_after": 0.5}), httpx.Response(204)]
    t = httpx.MockTransport(lambda r: respostas.pop(0))
    assert asyncio.run(discord_log.registrar("ban", "bob", transport=t)) is True
    assert esperas == [0.5]


def test_versao_sincrona(webhooks):
    enviados, _ = capturar()
    t = httpx.MockTransport(lambda r: (enviados.append(str(r.url)), httpx.Response(204))[1])
    assert discord_log.registrar_sync("desban", "bob", "", "admtest (ADM)", "Jogo ROLOX", transport=t)
    assert enviados == [URL_B]


def test_carregar_env_nao_sobrescreve(tmp_path, monkeypatch):
    arq = tmp_path / ".rolox.env"
    arq.write_text("# comentário\nexport ROLOX_WEBHOOK_BANIMENTOS='https://discord.com/api/webhooks/9/z'\n"
                   "DISCORD_TOKEN=abc\nOUTRA=ignorada\n", encoding="utf-8")
    monkeypatch.delenv("ROLOX_WEBHOOK_BANIMENTOS", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "ja-tinha")
    monkeypatch.delenv("OUTRA", raising=False)
    assert discord_log.carregar_env([arq]) == arq
    import os
    assert os.environ["ROLOX_WEBHOOK_BANIMENTOS"] == "https://discord.com/api/webhooks/9/z"
    assert os.environ["DISCORD_TOKEN"] == "ja-tinha" and "OUTRA" not in os.environ


def test_duracoes():
    assert [discord_log.formatar_duracao(m) for m in (1, 10, 60, 120, 1440, 10080)] == \
        ["1 minuto", "10 minutos", "1 hora", "2 horas", "1 dia", "7 dias"]


# ------------------------------------------------------------ respostas
@pytest.fixture
def respostas():
    return Respostas(PASTA.parent / "Fases" / "ROLOX_DISCORD.md")


def test_le_o_arquivo_do_discord(respostas):
    assert len(respostas.lista) >= 10
    assert "!fases" in respostas.comandos() and "!tickets" in respostas.comandos()
    assert all(len(r.texto) <= 2000 for r in respostas.lista)


def test_acha_por_comando(respostas):
    assert respostas.por_comando("!TICKETS").comando == "!tickets"
    assert respostas.por_comando("!studio agora") .comando == "!studio"
    assert respostas.por_comando("!naoexiste") is None


def test_acha_por_palavras_sem_acento(respostas):
    assert respostas.por_palavras("como ganho TICKETS?").comando == "!tickets"
    assert respostas.por_palavras("posso usar hack?").comando == "!hack"
    assert respostas.por_palavras("bom dia a todos") is None
    assert normalizar("Olá  MUNDO") == "ola mundo"


# ------------------------------------------------------------------ bot
def test_bot_tempo_e_criacao():
    pytest.importorskip("discord")
    import bot
    assert bot.ler_tempo("10m") == timedelta(minutes=10)
    assert bot.ler_tempo("2h") == timedelta(hours=2)
    assert bot.ler_tempo("1d") == timedelta(days=1)
    assert bot.ler_tempo("30") == timedelta(minutes=30)
    assert bot.ler_tempo("29d") is None and bot.ler_tempo("0m") is None and bot.ler_tempo("abc") is None
    b = bot.criar_bot(PASTA.parent / "Fases" / "ROLOX_DISCORD.md")
    assert {"ban", "desban", "semchat", "comchat", "aviso", "ajuda", "recarregar"} <= {c.name for c in b.commands}
    b.marcar(1, 2, "ban")
    assert b.ja_registrado(1, 2, "ban") and not b.ja_registrado(1, 2, "ban")


def test_copias_do_discord_log_iguais():
    original = (PASTA / "discord_log.py").read_text(encoding="utf-8")
    for copia in [PASTA.parent / "Rolox-App/mobile/src/rolox/discord_log.py", PASTA.parent / "Rolox-App/flask/discord_log.py"]:
        assert copia.read_text(encoding="utf-8") == original, f"{copia} desatualizada: copie de Rolox-Discord/discord_log.py"
