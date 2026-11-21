"""Tela do Atualizador do ROLOX."""

from __future__ import annotations

import asyncio
from typing import Optional

import flet as ft

from . import android
from .baixar import (ErroAtualizador, InfoVersao, PrecisaNavegador, baixar_arquivo, buscar_info, eh_mais_nova,
                     extrair_apk, tamanho_legivel)

COR = ft.Colors.DEEP_PURPLE
COR_DESTAQUE = ft.Colors.ORANGE_700
LINK_DISCORD = "https://discord.gg/6NZ5Ftq3p"
ESQUEMA_ROLOX = "rolox://abrir"

P_VERSAO = "atualizador.versao_baixada"      # versão (do Vision-apk-link.json) da última baixada
P_ATALHO = "atualizador.atalho_perguntado"


def logo(altura: int) -> ft.Control:
    return ft.Image(src="logo_nome.png", height=altura,
                    error_content=ft.Text("ROLOX", size=altura * 0.5, weight=ft.FontWeight.BOLD, color=COR))


class AtualizadorApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.prefs = ft.SharedPreferences()
        self.info: Optional[InfoVersao] = None
        self.apk_pronto = None              # Baixado, esperando instalar
        self.ocupado = False

    # ------------------------------------------------------------ preferências
    async def _get(self, k):
        try:
            return await self.prefs.get(k)
        except Exception:
            return None

    async def _set(self, k, v):
        try:
            await self.prefs.set(k, v)
        except Exception:
            pass

    def aviso(self, texto: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(texto), show_close_icon=True))

    # ------------------------------------------------------------------- tela
    async def iniciar(self) -> None:
        p = self.page
        p.title = "Atualizador do ROLOX"
        p.theme = ft.Theme(color_scheme_seed=COR)
        p.dark_theme = ft.Theme(color_scheme_seed=COR)
        p.theme_mode = ft.ThemeMode.SYSTEM
        p.padding = 0

        self.t_rolox = ft.Text("Procurando o ROLOX neste aparelho...", size=14)
        self.t_versao = ft.Text("Conferindo se tem versão nova...", size=14)
        self.t_status = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)
        self.barra = ft.ProgressBar(width=280, value=0, color=COR_DESTAQUE, visible=False, border_radius=4)
        self.b_baixar = ft.FilledButton("Baixar o ROLOX", icon=ft.Icons.DOWNLOAD, width=280, on_click=self.baixar)
        self.b_instalar = ft.FilledButton("Instalar agora", icon=ft.Icons.INSTALL_MOBILE, width=280,
                                          on_click=self.instalar, visible=False)
        self.b_jogar = ft.FilledButton("Jogar ROLOX", icon=ft.Icons.PLAY_ARROW, width=280, on_click=self.abrir_rolox,
                                       style=ft.ButtonStyle(bgcolor=COR_DESTAQUE, color=ft.Colors.WHITE))
        cartao = ft.Container(
            padding=16, border_radius=16, width=380,
            bgcolor=ft.Colors.with_opacity(0.08, COR),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, COR)),
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.SPORTS_ESPORTS, color=COR), self.t_rolox], wrap=True),
                ft.Row([ft.Icon(ft.Icons.SYSTEM_UPDATE, color=COR), self.t_versao], wrap=True),
            ], spacing=10),
        )
        p.controls.clear()
        p.add(ft.SafeArea(expand=True, content=ft.Container(
            padding=24, expand=True, alignment=ft.Alignment.CENTER,
            content=ft.Column([
                logo(76),
                ft.Text("Atualizador do ROLOX", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("O app oficial que baixa, atualiza e abre o ROLOX.", size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ft.Container(height=6),
                cartao,
                ft.Container(height=6),
                self.b_jogar, self.b_baixar, self.b_instalar, self.barra, self.t_status,
                ft.TextButton("Criar atalho do ROLOX na tela inicial", icon=ft.Icons.ADD_TO_HOME_SCREEN,
                              on_click=self.atalho),
                ft.TextButton("Discord do ROLOX", icon=ft.Icons.FORUM,
                              on_click=lambda _: p.run_task(ft.UrlLauncher().launch_url, LINK_DISCORD)),
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, tight=True, scroll=ft.ScrollMode.AUTO),
        )))
        p.update()
        await self.conferir()
        if not await self._get(P_ATALHO):
            await self._set(P_ATALHO, "1")
            self.perguntar_atalho()

    async def rolox_instalado(self) -> bool:
        if self.page.platform != ft.PagePlatform.ANDROID:
            return False
        try:
            return bool(await ft.UrlLauncher().can_launch_url(ESQUEMA_ROLOX))
        except Exception:
            return False

    async def conferir(self) -> None:
        instalado = await self.rolox_instalado()
        self.t_rolox.value = "ROLOX instalado ✅" if instalado else "ROLOX ainda não está instalado"
        self.b_jogar.visible = instalado
        self.page.update()
        try:
            self.info = await buscar_info()
        except ErroAtualizador as e:
            self.info = None
            self.t_versao.value = str(e)
            self.page.update()
            return
        baixada = await self._get(P_VERSAO)
        v = self.info.versao
        if instalado and not eh_mais_nova(v, baixada):
            self.t_versao.value = f"Você está na versão mais nova ({v}) 🎉"
            self.b_baixar.content = "Baixar de novo"
        elif instalado:
            self.t_versao.value = f"Tem versão nova do ROLOX: {v} ⬇️"
            self.b_baixar.content = f"Atualizar para a {v}"
        else:
            self.t_versao.value = f"Versão {v} pronta para baixar"
            self.b_baixar.content = f"Baixar o ROLOX {v}"
        self.page.update()

    # ------------------------------------------------------------------ ações
    async def baixar(self, _=None) -> None:
        if self.ocupado:
            return
        self.ocupado = True
        self.b_baixar.disabled = True
        self.barra.visible, self.barra.value = True, None
        self.t_status.value = "Baixando o ROLOX..."
        self.page.update()
        ultimo = [0.0]

        def progresso(feito: int, total: Optional[int]) -> None:
            agora = asyncio.get_event_loop().time()
            if agora - ultimo[0] < 0.15:
                return
            ultimo[0] = agora
            self.barra.value = (feito / total) if total else None
            self.t_status.value = f"Baixando o ROLOX... {tamanho_legivel(feito)}" + (f" de {tamanho_legivel(total)}" if total else "")
            self.page.update()

        try:
            if self.info is None:
                self.info = await buscar_info()
            dados = await baixar_arquivo(self.info.link, progresso)
            self.t_status.value = "Extraindo..."
            self.barra.value = None
            self.page.update()
            self.apk_pronto = await asyncio.to_thread(extrair_apk, dados, android.pasta_downloads())
            del dados
            await self._set(P_VERSAO, self.info.versao)
            self.t_status.value = f"Pronto: {self.apk_pronto.nome_original} ({tamanho_legivel(self.apk_pronto.tamanho)})"
            self.barra.visible = False
            self.b_instalar.visible = True
            self.page.update()
            await self.instalar()
        except PrecisaNavegador as e:
            # o link é uma página de download (ex.: TransferNow): o jogador baixa por lá
            self.barra.visible = False
            self.t_status.value = ("Abri a página de download no navegador. Baixe o arquivo do ROLOX, "
                                   "abra o .apk e toque em Instalar. Depois volte aqui e toque em Jogar.")
            await self._set(P_VERSAO, self.info.versao if self.info else "")
            try:
                await ft.UrlLauncher().launch_url(str(e), mode=ft.LaunchMode.EXTERNAL_APPLICATION)
            except Exception:
                self.aviso("Não deu para abrir o navegador.")
        except ErroAtualizador as e:
            self.barra.visible = False
            self.t_status.value = str(e)
            self.aviso(str(e))
        finally:
            self.ocupado = False
            self.b_baixar.disabled = False
            self.page.update()

    async def instalar(self, _=None) -> None:
        if not self.apk_pronto:
            return
        try:
            if not android.pode_instalar():
                self.pedir_permissao()
                return
            android.instalar_apk(self.apk_pronto.apk)
            self.t_status.value = "Toque em \"Instalar\" na janela do Android. Depois volte aqui e toque em Jogar."
        except android.SemAndroid:
            self.t_status.value = f"Instalar só funciona no Android. O arquivo está em: {self.apk_pronto.apk}"
        except Exception as e:
            self.t_status.value = f"Não deu para abrir o instalador: {e}"
        self.page.update()

    def pedir_permissao(self) -> None:
        def abrir(_):
            self.page.pop_dialog()
            try:
                android.pedir_permissao_instalar()
                self.t_status.value = "Permita \"Instalar apps desconhecidos\", volte e toque em Instalar agora."
                self.page.update()
            except Exception as e:
                self.aviso(f"Abra as configurações do Android e permita o Atualizador instalar apps ({e}).")
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Falta uma permissão"),
            content=ft.Text("Para instalar o ROLOX, o Android precisa deixar o Atualizador instalar apps. "
                            "Na próxima tela, ative \"Permitir desta fonte\" e depois volte aqui."),
            actions=[ft.TextButton("Agora não", on_click=lambda _: self.page.pop_dialog()),
                     ft.FilledButton("Abrir configurações", on_click=abrir)],
        ))

    async def abrir_rolox(self, _=None) -> None:
        try:
            await ft.UrlLauncher().launch_url(android.LINK_ROLOX)
        except Exception:
            self.aviso("Não achei o ROLOX. Baixe primeiro.")

    def perguntar_atalho(self) -> None:
        async def sim(_):
            self.page.pop_dialog()
            await self.atalho()
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Criar atalho do ROLOX?"),
            content=ft.Text("Coloque um atalho do ROLOX na tela inicial: ele abre o jogo direto, "
                            "sempre pela versão oficial."),
            actions=[ft.TextButton("Agora não", on_click=lambda _: self.page.pop_dialog()),
                     ft.FilledButton("Criar atalho", icon=ft.Icons.ADD_TO_HOME_SCREEN, on_click=sim)],
        ))

    async def atalho(self, _=None) -> None:
        try:
            if android.criar_atalho():
                self.aviso("Confirme \"Adicionar\" na janela do Android. O atalho ROLOX vai para a tela inicial.")
            else:
                self.aviso("A tela inicial deste aparelho não aceita atalhos. Use o botão Jogar ROLOX daqui.")
        except android.SemAndroid:
            self.aviso("O atalho só pode ser criado no Android.")
        except Exception as e:
            self.aviso(f"Não deu para criar o atalho: {e}")
