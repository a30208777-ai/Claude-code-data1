"""Atualizador do VISTA — ponto de entrada.

Rodar no PC para testar:   flet run src/main.py
Gerar APK:                 flet build apk   (ou pelo GitHub: .github/workflows/apk.yml)
"""

import flet as ft

from atualizador.telas import AtualizadorApp


async def main(page: ft.Page) -> None:
    await AtualizadorApp(page).iniciar()


if __name__ == "__main__":
    ft.run(main)
