"""Telas do Rolox Mobile (Flet)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Awaitable, Callable, Optional

import flet as ft

from . import config
from .api import ErroRolox, RoloxAPI

CHAVE_REFRESH = "rolox.refresh_token"

COR_PRIMARIA = ft.Colors.DEEP_PURPLE
COR_HACK = ft.Colors.ORANGE_700


def formatar_data(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except (ValueError, AttributeError):
        return iso or ""


class RoloxApp:
    def __init__(self, page: ft.Page, api: Optional[RoloxAPI] = None):
        self.page = page
        self.api = api or RoloxAPI()
        self.prefs = ft.SharedPreferences()
        self.geracao = 0          # muda a cada troca de tela; encerra os loops antigos
        self.perfil: dict = {}
        self.jogos: list[dict] = []
        self.servidor_atual: Optional[dict] = None

    # ================================================================ base
    async def iniciar(self) -> None:
        p = self.page
        p.title = "Rolox"
        p.theme = ft.Theme(color_scheme_seed=COR_PRIMARIA)
        p.dark_theme = ft.Theme(color_scheme_seed=COR_PRIMARIA)
        p.theme_mode = ft.ThemeMode.SYSTEM
        p.padding = 0

        token = await self._pref_get(CHAVE_REFRESH)
        if token:
            try:
                await self.api.renovar(token)
                await self._salvar_sessao()
                await self.abrir_principal()
                return
            except ErroRolox:
                await self._pref_remove(CHAVE_REFRESH)
        self.tela_login()

    async def _pref_get(self, chave: str):
        try:
            return await self.prefs.get(chave)
        except Exception:
            return None

    async def _pref_remove(self, chave: str) -> None:
        try:
            await self.prefs.remove(chave)
        except Exception:
            pass

    async def _salvar_sessao(self) -> None:
        if self.api.sessao:
            try:
                await self.prefs.set(CHAVE_REFRESH, self.api.sessao.refresh_token)
            except Exception:
                pass

    def aviso(self, texto: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(texto), show_close_icon=True))

    def mostrar(self, conteudo: ft.Control, nav: Optional[ft.NavigationBar] = None) -> int:
        self.geracao += 1
        self.page.controls.clear()
        self.page.navigation_bar = nav
        self.page.add(ft.SafeArea(content=conteudo, expand=True))
        self.page.update()
        return self.geracao

    def repetir(self, geracao: int, intervalo: float, acao: Callable[[], Awaitable[None]]) -> None:
        """Roda `acao` a cada `intervalo` s enquanto a tela não mudar."""
        async def laco():
            while self.geracao == geracao:
                try:
                    await acao()
                except ErroRolox as e:
                    if e.codigo == "sessao_expirada":
                        await self.sair_da_conta(aviso_texto=e.mensagem)
                        return
                except Exception:
                    pass
                await asyncio.sleep(intervalo)
        self.page.run_task(laco)

    async def executar(self, acao: Callable[[], Awaitable[None]]) -> None:
        """Roda uma ação de botão mostrando erros como aviso."""
        try:
            await acao()
        except ErroRolox as e:
            if e.codigo == "sessao_expirada":
                await self.sair_da_conta(aviso_texto=e.mensagem)
            else:
                self.aviso(e.mensagem)
        except ValueError as e:
            self.aviso(str(e))

    def nome_jogo(self, gameid: Optional[str]) -> str:
        for j in self.jogos:
            if j["gameid"] == gameid:
                return j["nome"]
        return gameid or "—"

    # =============================================================== login
    def tela_login(self) -> None:
        usuario = ft.TextField(label="Usuário", autofocus=True, autocorrect=False,
                               capitalization=ft.TextCapitalization.NONE)
        senha = ft.TextField(label="Senha", password=True, can_reveal_password=True)
        carregando = ft.ProgressRing(visible=False, width=24, height=24)

        async def entrar(_=None):
            carregando.visible = True
            botao.disabled = True
            self.page.update()
            try:
                async def acao():
                    await self.api.login(usuario.value or "", senha.value or "")
                    await self._salvar_sessao()
                    await self.abrir_principal()
                await self.executar(acao)
            finally:
                carregando.visible = False
                botao.disabled = False
                senha.value = ""
                self.page.update()

        senha.on_submit = entrar
        botao = ft.FilledButton("Entrar", on_click=entrar, expand=True)

        self.mostrar(ft.Container(
            padding=24,
            content=ft.Column(
                [
                    ft.Text("ROLOX", size=40, weight=ft.FontWeight.BOLD, color=COR_PRIMARIA),
                    ft.Text("Entre na sua conta"),
                    usuario,
                    senha,
                    ft.Row([botao, carregando]),
                    ft.TextButton("Criar conta", on_click=lambda _: self.tela_cadastro()),
                    ft.Text("3 senhas erradas bloqueiam o aparelho que errou, "
                            "e o dono da conta é avisado.", size=12, italic=True),
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
        ))

    def tela_cadastro(self) -> None:
        usuario = ft.TextField(label="Usuário", helper="minúsculas, números e hífen (3 a 32)",
                               capitalization=ft.TextCapitalization.NONE, autocorrect=False)
        senha = ft.TextField(label="Senha (mín. 8)", password=True, can_reveal_password=True)
        email = ft.TextField(label="E-mail (opcional)", keyboard_type=ft.KeyboardType.EMAIL,
                             helper="pode adicionar depois em Perfil")
        local = ft.Switch(label="Mostrar para amigos onde estou jogando", value=False)

        async def cadastrar(_):
            async def acao():
                await self.api.cadastrar(usuario.value or "", senha.value or "",
                                         bool(local.value), email.value or "")
                await self._salvar_sessao()
                await self.abrir_principal()
                self.aviso("Conta criada! Bem-vindo ao Rolox.")
            await self.executar(acao)

        self.mostrar(ft.Container(
            padding=24,
            content=ft.Column(
                [
                    ft.Text("Criar conta", size=28, weight=ft.FontWeight.BOLD),
                    usuario, senha, email, local,
                    ft.Text("Seu IP e sua localização na plataforma só são usados para "
                            "segurança e status online (LGPD).", size=12, italic=True),
                    ft.FilledButton("Cadastrar", on_click=cadastrar),
                    ft.TextButton("Já tenho conta", on_click=lambda _: self.tela_login()),
                ],
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
            ),
        ))

    async def sair_da_conta(self, aviso_texto: Optional[str] = None) -> None:
        await self.api.sair_da_conta()
        await self._pref_remove(CHAVE_REFRESH)
        self.perfil, self.servidor_atual = {}, None
        self.tela_login()
        if aviso_texto:
            self.aviso(aviso_texto)

    # ======================================================== área logada
    async def abrir_principal(self, aba: int = 0) -> None:
        self.perfil = await self.api.meu_perfil()
        self.jogos = await self.api.jogos()
        onde = await self.api.onde_estou()
        if onde["servidor"]:
            servidores = await self.api.servidores()
            self.servidor_atual = next(
                (s for s in servidores if s["server_uid"] == onde["servidor"]), None)
            if self.servidor_atual:
                self.tela_chat()
                return
        try:
            await self.api.atualizar_local("menu")
        except ErroRolox:
            pass
        self.abrir_aba(aba)

    def barra(self, indice: int) -> ft.NavigationBar:
        return ft.NavigationBar(
            selected_index=indice,
            on_change=lambda e: self.abrir_aba(int(e.control.selected_index)),
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Início"),
                ft.NavigationBarDestination(icon=ft.Icons.DNS, label="Servidores"),
                ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="Perfil"),
            ],
        )

    def abrir_aba(self, indice: int) -> None:
        [self.aba_inicio, self.aba_servidores, self.aba_perfil][indice]()

    # --------------------------------------------------------------- início
    def aba_inicio(self) -> None:
        status = ft.Text("")
        lista = ft.ListView(expand=True, spacing=6)

        def item_alerta(a: dict) -> ft.Control:
            async def ver(_):
                async def acao():
                    senha = await self.api.ver_senha_tentada(a["id"])
                    self.page.show_dialog(ft.AlertDialog(
                        title=ft.Text("Senha usada na tentativa"),
                        content=ft.Text(senha, selectable=True, size=18),
                        actions=[ft.TextButton("Fechar", on_click=lambda _: self.page.pop_dialog())],
                    ))
                    await atualizar()
                await self.executar(acao)

            sub = f"IP {a['ip']} · {formatar_data(a['criado_em'])}"
            if a["ip_foi_banido"]:
                sub += " · IP banido"
            return ft.Card(content=ft.ListTile(
                leading=ft.Icon(ft.Icons.WARNING, color=ft.Colors.RED if not a["lido"] else None),
                title=ft.Text("Alguém tentou entrar na sua conta",
                              weight=None if a["lido"] else ft.FontWeight.BOLD),
                subtitle=ft.Text(sub),
                trailing=ft.IconButton(ft.Icons.VISIBILITY, tooltip="Ver senha usada", on_click=ver),
            ))

        async def atualizar():
            onde = await self.api.onde_estou()
            if onde["servidor"]:
                status.value = "Você está em um servidor."
            elif onde["fila"]:
                status.value = f"Na fila de espera — posição {onde['posicao']}."
            else:
                status.value = "Você está no lobby."
            alertas = await self.api.alertas()
            lista.controls = [item_alerta(a) for a in alertas] or [
                ft.Text("Nenhuma tentativa suspeita na sua conta. 👍")]
            if onde["servidor"] and self.geracao == ger:
                servidores = await self.api.servidores()
                self.servidor_atual = next(
                    (s for s in servidores if s["server_uid"] == onde["servidor"]), None)
                if self.servidor_atual:
                    self.tela_chat()
                    return
            self.page.update()

        ger = self.mostrar(ft.Container(
            padding=16,
            content=ft.Column([
                ft.Text(f"Olá, {self.perfil.get('username', '')}!", size=24,
                        weight=ft.FontWeight.BOLD),
                status,
                ft.Divider(),
                ft.Row([ft.Icon(ft.Icons.SHIELD), ft.Text("Alertas de segurança", size=18)]),
                lista,
            ], expand=True),
        ), self.barra(0))
        self.repetir(ger, config.INTERVALO_ALERTAS, atualizar)

    # ----------------------------------------------------------- servidores
    def aba_servidores(self) -> None:
        lista = ft.ListView(expand=True, spacing=6)
        so_meu_modo = ft.Switch(label="Só servidores que posso entrar", value=True)

        def pode_entrar(s: dict) -> bool:
            com_hack = self.perfil.get("jogo_mod") == s["gameid"]
            return com_hack == s["is_hack_server"]

        def card(s: dict) -> ft.Control:
            async def entrar(_):
                async def acao():
                    r = await self.api.entrar(s["server_uid"])
                    if r["resultado"] == "fila":
                        self.aviso(f"Servidor cheio. Você está na fila, posição {r['posicao']}.")
                        self.aba_inicio()
                    else:
                        self.servidor_atual = s
                        self.tela_chat()
                await self.executar(acao)

            etiquetas = [ft.Text(f"{s['jogadores']}/{s['capacidade']} jogadores")]
            if s["is_hack_server"]:
                etiquetas.append(ft.Container(
                    ft.Text("HACK/MOD", size=11, color=ft.Colors.WHITE),
                    bgcolor=COR_HACK, padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=6))
            return ft.Card(content=ft.ListTile(
                title=ft.Text(self.nome_jogo(s["gameid"]), weight=ft.FontWeight.BOLD),
                subtitle=ft.Row(etiquetas, spacing=8),
                trailing=ft.FilledButton(
                    "Fila" if s["status"] == "cheio" else "Entrar", on_click=entrar),
            ))

        async def atualizar():
            servidores = await self.api.servidores()
            if so_meu_modo.value:
                servidores = [s for s in servidores if pode_entrar(s)]
            lista.controls = [card(s) for s in servidores] or [
                ft.Text("Nenhum servidor aberto. Crie o primeiro!")]
            self.page.update()

        async def ao_filtrar(_):
            await self.executar(atualizar)

        so_meu_modo.on_change = ao_filtrar

        ger = self.mostrar(ft.Container(
            padding=16,
            content=ft.Column([
                ft.Row([
                    ft.Text("Servidores", size=24, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.ADD, tooltip="Criar servidor",
                                  on_click=lambda _: self.dialogo_criar_servidor()),
                ]),
                so_meu_modo,
                lista,
            ], expand=True),
        ), self.barra(1))
        self.repetir(ger, config.INTERVALO_SERVIDORES, atualizar)

    def dialogo_criar_servidor(self) -> None:
        if not self.jogos:
            self.aviso("Nenhum jogo aprovado no catálogo ainda.")
            return
        jogo = ft.Dropdown(
            label="Jogo", value=self.jogos[0]["gameid"],
            options=[ft.DropdownOption(key=j["gameid"], text=j["nome"]) for j in self.jogos])
        capacidade = ft.TextField(label="Capacidade (1–100)", value="10",
                                  keyboard_type=ft.KeyboardType.NUMBER)
        hack = ft.Switch(label="Servidor de hack/mod", value=False)

        async def criar(_):
            async def acao():
                try:
                    cap = int(capacidade.value or "0")
                except ValueError:
                    raise ValueError("Capacidade precisa ser um número.")
                s = await self.api.criar_servidor(jogo.value, cap, bool(hack.value))
                self.page.pop_dialog()
                r = await self.api.entrar(s["server_uid"])
                if r["resultado"] in ("entrou", "ja_esta"):
                    s["jogadores"] = 1
                    self.servidor_atual = s
                    self.tela_chat()
            await self.executar(acao)

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Criar servidor"),
            content=ft.Column([jogo, capacidade, hack], tight=True, spacing=12),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton("Criar", on_click=criar),
            ],
        ))

    # ------------------------------------------------------------------ chat
    def tela_chat(self) -> None:
        s = self.servidor_atual
        if not s:
            self.abrir_aba(1)
            return
        uid = s["server_uid"]
        eu_sou_host = s.get("host_id") == self.api.user_id
        mensagens = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        campo = ft.TextField(hint_text="Mensagem", expand=True, max_length=500,
                             shift_enter=True)
        ultimo_id = 0

        async def puxar():
            nonlocal ultimo_id
            novas = await self.api.mensagens(uid, ultimo_id)
            for m in novas:
                ultimo_id = max(ultimo_id, m["id"])
                mensagens.controls.append(ft.Text(spans=[
                    ft.TextSpan(f"{m['username']}: ", ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    ft.TextSpan(m["mensagem_filtrada"]),
                ], selectable=True))
            onde = await self.api.onde_estou()
            if onde["servidor"] != uid and self.geracao == ger:
                self.servidor_atual = None
                self.aviso("Você saiu do servidor (ele foi encerrado ou você foi removido).")
                self.abrir_aba(1)
                return
            self.page.update()

        async def enviar(_=None):
            texto = (campo.value or "").strip()
            if not texto:
                return
            async def acao():
                await self.api.enviar(uid, texto, self.perfil.get("idioma"))
                campo.value = ""
                await puxar()
            await self.executar(acao)
            await campo.focus()

        async def sair(_):
            async def acao():
                await self.api.sair(uid)
                self.servidor_atual = None
                self.abrir_aba(1)
            await self.executar(acao)

        async def pulso():
            await self.api.heartbeat(uid)

        campo.on_submit = enviar
        titulo = self.nome_jogo(s["gameid"]) + ("  ·  HACK/MOD" if s["is_hack_server"] else "")

        ger = self.mostrar(ft.Container(
            padding=12,
            content=ft.Column([
                ft.Row([
                    ft.Text(titulo, size=20, weight=ft.FontWeight.BOLD, expand=True),
                    ft.OutlinedButton("Sair", icon=ft.Icons.EXIT_TO_APP, on_click=sair),
                ]),
                ft.Text("O chat passa pelo filtro SELECT antes de ser entregue.",
                        size=12, italic=True),
                ft.Divider(),
                mensagens,
                ft.Row([campo, ft.IconButton(ft.Icons.SEND, on_click=enviar)]),
            ], expand=True),
        ))
        self.repetir(ger, config.INTERVALO_CHAT, puxar)
        if eu_sou_host:
            self.repetir(ger, config.INTERVALO_HEARTBEAT, pulso)

    # ---------------------------------------------------------------- perfil
    def aba_perfil(self) -> None:
        p = self.perfil
        idioma = ft.Dropdown(
            label="Idioma do chat", value=p.get("idioma", "pt-BR"),
            options=[ft.DropdownOption(key=k, text=v) for k, v in config.IDIOMAS.items()])
        jogo_mod = ft.Dropdown(
            label="Jogo onde uso hack/mod", value=p.get("jogo_mod") or "",
            options=[ft.DropdownOption(key="", text="Nenhum (jogo limpo)")]
            + [ft.DropdownOption(key=j["gameid"], text=j["nome"]) for j in self.jogos])
        local = ft.Switch(label="Mostrar onde estou para amigos",
                          value=bool(p.get("aceitou_localizacao")))
        email = ft.TextField(label="E-mail (opcional)", value=p.get("email") or "",
                             keyboard_type=ft.KeyboardType.EMAIL,
                             helper="deixe vazio para remover")

        async def salvar(_):
            async def acao():
                novo_mod = jogo_mod.value or None
                self.perfil = await self.api.atualizar_perfil(
                    idioma=idioma.value, jogo_mod=novo_mod,
                    aceitou_localizacao=bool(local.value), email=email.value or "")
                await self.api.atualizar_local("menu")
                self.aviso("Perfil salvo.")
            await self.executar(acao)

        async def sair(_):
            await self.sair_da_conta()

        self.mostrar(ft.Container(
            padding=16,
            content=ft.Column([
                ft.Text(p.get("username", ""), size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Configurações (config)", size=16),
                idioma,
                jogo_mod,
                ft.Text("Com hack/mod marcado, você só entra nos servidores de hack desse "
                        "jogo. Pode trocar a qualquer momento.", size=12, italic=True),
                local,
                email,
                ft.FilledButton("Salvar", on_click=salvar),
                ft.Divider(),
                ft.OutlinedButton("Sair da conta", icon=ft.Icons.LOGOUT, on_click=sair),
            ], spacing=14, scroll=ft.ScrollMode.AUTO),
        ), self.barra(2))
