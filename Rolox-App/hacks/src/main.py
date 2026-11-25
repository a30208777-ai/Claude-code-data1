"""VISTA Hacks — app dos servidores de hack/mod do VISTA.

As pessoas daqui NÃO jogam com os jogadores do VISTA normal: entram em servidores de hack/mod
(o banco do VISTA separa) e, no jogo, o botão 🤖 lá em cima abre o executor de scripts.
O jogo roda no site do VISTA (área /hacks), aberto dentro do app.

Rodar no PC para testar:   flet run src/main.py      (no PC abre no navegador)
Gerar APK:                 flet build apk   (ou pelo GitHub: .github/workflows/apk.yml)
"""

import os

import flet as ft

SITE = os.environ.get("ROLOX_SITE_URL", "https://rolox-gj2i.onrender.com").rstrip("/")
URL_HACKS = f"{SITE}/hacks"
COR = "#ff6d00"


def tem_webview(page: ft.Page) -> bool:
    return page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS, ft.PagePlatform.MACOS)


async def main(page: ft.Page) -> None:
    page.title = "VISTA Hacks"
    page.theme = ft.Theme(color_scheme_seed=COR)
    page.dark_theme = ft.Theme(color_scheme_seed=COR)
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = "#120612"

    async def abrir_navegador(_=None):
        await ft.UrlLauncher().launch_url(URL_HACKS)

    if not tem_webview(page):
        # PC/navegador: o WebView do Flet não existe aqui -> abre a área de hacks no navegador
        page.add(ft.SafeArea(expand=True, content=ft.Container(
            expand=True, alignment=ft.Alignment.CENTER, padding=24,
            content=ft.Column([
                ft.Image(src="logo_nome.png", height=72),
                ft.Text("Servidores de hack/mod do VISTA, separados dos jogadores normais. "
                        "No jogo, o botão 🤖 lá em cima abre o executor de scripts.", text_align=ft.TextAlign.CENTER),
                ft.FilledButton("Abrir o VISTA Hacks", icon=ft.Icons.OPEN_IN_BROWSER, on_click=abrir_navegador),
            ], tight=True, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )))
        return

    import flet_webview as fwv

    progresso = ft.ProgressBar(color=COR, bar_height=3, visible=True)

    def comecou(_):
        progresso.visible = True
        page.update()

    def terminou(_):
        progresso.visible = False
        page.update()

    def falhou(e):
        progresso.visible = False
        page.show_dialog(ft.SnackBar(ft.Text("Sem conexão com o VISTA. Confira a internet e toque em ⟳."),
                                     show_close_icon=True))
        page.update()

    web = fwv.WebView(url=URL_HACKS, expand=True, bgcolor="#120612",
                      on_page_started=comecou, on_page_ended=terminou, on_web_resource_error=falhou)

    async def voltar(_=None):
        if await web.can_go_back():
            await web.go_back()

    async def recarregar(_=None):
        await web.reload()

    async def inicio(_=None):
        await web.load_request(URL_HACKS)

    barra = ft.Container(
        bgcolor="#1c0a1e", padding=ft.Padding.symmetric(horizontal=6, vertical=2),
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Voltar", on_click=voltar, icon_color=ft.Colors.WHITE),
            ft.Image(src="logo_nome.png", height=26),
            ft.Container(expand=True),
            ft.IconButton(ft.Icons.HOME, tooltip="Jogos com hack", on_click=inicio, icon_color=ft.Colors.WHITE),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Recarregar", on_click=recarregar, icon_color=ft.Colors.WHITE),
        ], spacing=4),
    )
    page.add(ft.SafeArea(expand=True, content=ft.Column([barra, progresso, web], spacing=0, expand=True)))


if __name__ == "__main__":
    ft.run(main)
