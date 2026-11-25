"""Proteção contra cópia pirata: o VISTA só abre se o "Atualizador do VISTA" estiver no aparelho.

O Atualizador é o app oficial que baixa e atualiza o VISTA. Os dois se reconhecem por links
próprios (deep links): o VISTA responde a  rolox://  e o Atualizador a  roloxatualizador://.
O VISTA pergunta ao Android se alguém abre  roloxatualizador://  — se ninguém abre, o
Atualizador não está instalado.

Só vale no Android (no PC e no navegador é ambiente de teste/desenvolvimento).
Quem abre sem o Atualizador vê um aviso; a partir da 3ª vez (do mesmo usuário) o aviso fica sério.
"""

from __future__ import annotations

ESQUEMA_ATUALIZADOR = "roloxatualizador://verificar"
LINK_DISCORD = "https://discord.gg/6NZ5Ftq3p"
LINK_DOWNLOAD = ""            # ainda não existe: quando existir, coloque aqui o link do Atualizador
VEZES_PARA_AVISO_SERIO = 3

CHAVE_CONTADOR = "rolox.sem_atualizador."      # + nome do usuário (ou "aparelho")
CHAVE_ULTIMO_USUARIO = "rolox.ultimo_usuario"

TITULO_PIRATA = "Ei!, abaixou uma cópia pirata?"
TEXTO_PIRATA = "Enfim, entre no nosso Discord e abaixe o app."
TITULO_BAN = "EI! VOCÊ PODE SER BANIDO!"


def texto_ban() -> str:
    return "ABAIXE O APP POR: " + (LINK_DOWNLOAD or "(link de download em breve)")


def chave_contador(usuario: str | None) -> str:
    nome = "".join(c for c in (usuario or "").lower() if c.isalnum() or c in "._-")[:40]
    return CHAVE_CONTADOR + (nome or "aparelho")


def aviso_para(vezes: int) -> tuple[str, str, bool]:
    """(título, texto, é_sério) para a N-ésima vez que abriu sem o Atualizador."""
    if vezes >= VEZES_PARA_AVISO_SERIO:
        return TITULO_BAN, texto_ban(), True
    return TITULO_PIRATA, TEXTO_PIRATA, False


async def atualizador_instalado(page) -> bool:
    """True se o Atualizador está no aparelho (ou se não é Android: lá não exigimos)."""
    import os
    import flet as ft
    if os.environ.get("ROLOX_SIMULAR_SEM_ATUALIZADOR") == "1":    # só para testar a tela no PC
        return False
    if page.platform != ft.PagePlatform.ANDROID:
        return True
    try:
        return bool(await ft.UrlLauncher().can_launch_url(ESQUEMA_ATUALIZADOR))
    except Exception:
        return True          # não conseguiu perguntar ao Android: não bloqueia o jogador por erro nosso
