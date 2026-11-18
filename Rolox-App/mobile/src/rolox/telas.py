"""Telas do Rolox Mobile (Flet)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Awaitable, Callable, Optional

import flet as ft

from . import avatar as avatar_mod
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


def desenhar_avatar(avatar: Optional[dict], escala: float = 1.0) -> ft.Control:
    """Desenha o boneco em blocos (ver rolox/avatar.py)."""
    return ft.Stack(
        width=avatar_mod.LARGURA * escala, height=avatar_mod.ALTURA * escala,
        controls=[ft.Container(left=x * escala, top=y * escala, width=w * escala, height=h * escala,
                               bgcolor=cor, border_radius=r * escala)
                  for x, y, w, h, cor, r in avatar_mod.pecas(avatar)],
    )


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
        local = ft.Switch(label="Mostrar para amigos onde estou jogando", value=False)

        async def cadastrar(_):
            async def acao():
                await self.api.cadastrar(usuario.value or "", senha.value or "",
                                         bool(local.value))
                await self._salvar_sessao()
                await self.abrir_principal()
                self.aviso("Conta criada! Bem-vindo ao Rolox.")
            await self.executar(acao)

        self.mostrar(ft.Container(
            padding=24,
            content=ft.Column(
                [
                    ft.Text("Criar conta", size=28, weight=ft.FontWeight.BOLD),
                    usuario, senha, local,
                    ft.Text("Você pode adicionar um e-mail depois, em Perfil.",
                            size=12, italic=True),
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
        try:
            presente = await self.api.receber_tickets()
            if presente.get("ganhou"):
                self.perfil["tickets"] = presente["tickets"]
                self.aviso(f"Presente do dia: +{presente['ganhou']} tickets! "
                           f"Amanhã você ganha {presente['amanha']}.")
        except ErroRolox:
            pass
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
            ] + ([ft.NavigationBarDestination(icon=ft.Icons.ADMIN_PANEL_SETTINGS, label="ADM")]
                 if self.perfil.get("is_adm") else []),
        )

    def abrir_aba(self, indice: int) -> None:
        abas = [self.aba_inicio, self.aba_servidores, self.aba_perfil]
        if self.perfil.get("is_adm"):
            abas.append(self.aba_adm)
        abas[min(indice, len(abas) - 1)]()

    def texto_tickets(self) -> str:
        if self.perfil.get("is_adm"):
            return "Tickets: ∞ (ADM)"
        return f"Tickets: {self.perfil.get('tickets', 0)}"

    def linha_tickets(self) -> ft.Control:
        return ft.Row([ft.Icon(ft.Icons.CONFIRMATION_NUMBER, size=18, color=COR_HACK),
                       ft.Text(self.texto_tickets(), weight=ft.FontWeight.BOLD)], spacing=6)

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
                ft.Row([
                    desenhar_avatar(self.perfil.get("avatar"), 0.4),
                    ft.Column([
                        ft.Text(f"Olá, {self.perfil.get('username', '')}!", size=24,
                                weight=ft.FontWeight.BOLD),
                        status,
                        self.linha_tickets(),
                        ft.Text("1 ticket = 1 resposta de IA no chat. Todo dia tem presente!",
                                size=12, italic=True),
                    ], spacing=4, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
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

            texto = f"{s['jogadores']}/{s['capacidade']} jogadores"
            if s.get("ias"):
                texto += f" ({s['ias']} IA)"
            etiquetas = [ft.Text(texto)]
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
                    s["jogadores"] = 1 + cap // 2   # você + as IAs (metade, para baixo)
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
                    ft.TextSpan(f"{m['username']}", ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    ft.TextSpan(" IA" if m.get("bot_id") else "",
                                ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=COR_HACK)),
                    ft.TextSpan(": ", ft.TextStyle(weight=ft.FontWeight.BOLD)),
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
                ft.Text("O chat passa pelo filtro SELECT. Cada resposta de IA usa 1 ticket seu "
                        f"({self.texto_tickets().replace('Tickets: ', '')}).",
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

        # ---- editor de avatar (primeiro passo)
        escolha = avatar_mod.normalizar(p.get("avatar"))
        previa = ft.Container(content=desenhar_avatar(escolha, 0.9), alignment=ft.Alignment.CENTER)

        def seletor(rotulo: str, chave: str, opcoes: dict) -> ft.Dropdown:
            # opcoes: nome -> valor (cores) ou valor -> nome (estilos)
            if chave in ("cabelo", "acessorio"):
                itens = [ft.DropdownOption(key=k, text=v) for k, v in opcoes.items()]
            else:
                itens = [ft.DropdownOption(key=v, text=n) for n, v in opcoes.items()]

            def mudou(e):
                escolha[chave] = e.control.value
                previa.content = desenhar_avatar(escolha, 0.9)
                previa.update()

            return ft.Dropdown(label=rotulo, value=escolha[chave], options=itens,
                               on_select=mudou, expand=True)

        editor = ft.Column([
            ft.Row([seletor("Pele", "pele", avatar_mod.PELES),
                    seletor("Cabelo", "cabelo", avatar_mod.CABELOS)]),
            ft.Row([seletor("Cor do cabelo", "cor_cabelo", avatar_mod.CORES),
                    seletor("Acessório", "acessorio", avatar_mod.ACESSORIOS)]),
            ft.Row([seletor("Camisa", "camisa", avatar_mod.CORES),
                    seletor("Calça", "calca", avatar_mod.CORES)]),
        ], spacing=10)

        async def salvar(_):
            async def acao():
                novo_mod = jogo_mod.value or None
                self.perfil = await self.api.atualizar_perfil(
                    idioma=idioma.value, jogo_mod=novo_mod,
                    aceitou_localizacao=bool(local.value), email=email.value or "",
                    avatar=escolha)
                await self.api.atualizar_local("menu")
                self.aviso("Perfil salvo.")
            await self.executar(acao)

        async def sair(_):
            await self.sair_da_conta()

        self.mostrar(ft.Container(
            padding=16,
            content=ft.Column([
                ft.Text(p.get("username", ""), size=24, weight=ft.FontWeight.BOLD),
                self.linha_tickets(),
                ft.Text("Avatar", size=16),
                previa,
                editor,
                ft.Divider(),
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

    # ------------------------------------------------------------------ ADM
    def aba_adm(self) -> None:
        resumo = ft.Text("")
        usuarios = ft.Column(spacing=6)
        ips = ft.Column(spacing=6)
        servidores = ft.Column(spacing=6)

        def secao(titulo: str, icone, corpo: ft.Control) -> ft.Control:
            return ft.Column([ft.Row([ft.Icon(icone), ft.Text(titulo, size=18)]), corpo], spacing=6)

        async def carregar(_=None):
            async def acao():
                d = await self.api.adm_painel()
                t = d["totais"]
                resumo.value = (f"{t['usuarios']} usuários · {t['servidores']} servidores · "
                                f"{t['ips_bloqueados']} IPs bloqueados · {t['alertas_hoje']} alertas hoje")
                usuarios.controls = [cartao_usuario(u) for u in d["usuarios"]] or [ft.Text("Nenhum.")]
                ips.controls = [cartao_ip(i) for i in d["ips_bloqueados"]] or [ft.Text("Nenhum IP bloqueado.")]
                servidores.controls = [cartao_servidor(s) for s in d["servidores"]] or [ft.Text("Nenhum servidor.")]
                self.page.update()
            await self.executar(acao)

        def acao_e_recarrega(fn, texto_ok: str):
            async def clique(_):
                async def acao():
                    await fn()
                    self.aviso(texto_ok)
                    await carregar()
                await self.executar(acao)
            return clique

        def cartao_usuario(u: dict) -> ft.Control:
            eu = u["id"] == self.api.user_id
            tickets = "∞" if u["is_adm"] else str(u["tickets"])
            marcas = (" · ADM" if u["is_adm"] else "") + (" · BANIDO" if u["banido"] else "")

            def dar_tickets(_):
                campo = ft.TextField(label="Quantidade (use - para tirar)", value="10",
                                     keyboard_type=ft.KeyboardType.NUMBER)

                async def confirmar(_):
                    async def acao():
                        try:
                            qtd = int(campo.value or "0")
                        except ValueError:
                            raise ValueError("Digite um número.")
                        self.page.pop_dialog()
                        await self.api.adm_dar_tickets(u["id"], qtd)
                        self.aviso(f"Tickets de {u['username']} ajustados.")
                        await carregar()
                    await self.executar(acao)

                self.page.show_dialog(ft.AlertDialog(
                    title=ft.Text(f"Tickets para {u['username']}"), content=campo,
                    actions=[ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                             ft.FilledButton("Confirmar", on_click=confirmar)]))

            botoes = []
            if not u["is_adm"]:
                botoes.append(ft.IconButton(ft.Icons.CONFIRMATION_NUMBER, tooltip="Dar/tirar tickets",
                                            on_click=dar_tickets))
            if not eu:
                if u["banido"]:
                    botoes.append(ft.IconButton(ft.Icons.LOCK_OPEN, tooltip="Desbanir", on_click=acao_e_recarrega(
                        lambda: self.api.adm_desbanir(u["id"]), f"{u['username']} desbanido.")))
                else:
                    botoes.append(ft.IconButton(ft.Icons.BLOCK, tooltip="Banir", on_click=acao_e_recarrega(
                        lambda: self.api.adm_banir(u["id"], "banido por ADM"), f"{u['username']} banido.")))
                botoes.append(ft.IconButton(
                    ft.Icons.REMOVE_MODERATOR if u["is_adm"] else ft.Icons.ADD_MODERATOR,
                    tooltip="Tirar ADM" if u["is_adm"] else "Tornar ADM",
                    on_click=acao_e_recarrega(lambda: self.api.adm_definir_adm(u["id"], not u["is_adm"]),
                                              "Permissão de ADM alterada.")))
            return ft.Card(content=ft.ListTile(
                title=ft.Text(u["username"] + (" (você)" if eu else "")),
                subtitle=ft.Text(f"Tickets: {tickets}{marcas}"),
                trailing=ft.Row(botoes, tight=True, spacing=0)))

        def cartao_ip(i: dict) -> ft.Control:
            return ft.Card(content=ft.ListTile(
                title=ft.Text(i["ip"]),
                subtitle=ft.Text(f"tentou entrar em {i.get('conta_alvo') or '?'} · {formatar_data(i['bloqueado_em'])}"),
                trailing=ft.TextButton("Desbloquear", on_click=acao_e_recarrega(
                    lambda: self.api.adm_desbloquear_ip(i["ip"]), f"IP {i['ip']} desbloqueado."))))

        def cartao_servidor(s: dict) -> ft.Control:
            return ft.Card(content=ft.ListTile(
                title=ft.Text(self.nome_jogo(s["gameid"]) + (" · HACK/MOD" if s["is_hack_server"] else "")),
                subtitle=ft.Text(f"{s['humanos'] + s['ias']}/{s['capacidade']} ({s['ias']} IA)"),
                trailing=ft.TextButton("Encerrar", on_click=acao_e_recarrega(
                    lambda: self.api.adm_encerrar_servidor(s["server_uid"]), "Servidor encerrado."))))

        self.mostrar(ft.Container(
            padding=16,
            content=ft.Column([
                ft.Row([ft.Text("Painel ADM", size=24, weight=ft.FontWeight.BOLD, expand=True),
                        ft.IconButton(ft.Icons.REFRESH, tooltip="Atualizar", on_click=carregar)]),
                resumo,
                secao("Usuários", ft.Icons.PEOPLE, usuarios),
                secao("IPs bloqueados", ft.Icons.SHIELD, ips),
                secao("Servidores", ft.Icons.DNS, servidores),
            ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
        ), self.barra(3))
        self.page.run_task(carregar)
