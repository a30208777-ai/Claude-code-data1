"""Rolox Mobile — ponto de entrada.

Rodar no PC para testar:   flet run src/main.py
Rodar no celular (dev):    flet run --android src/main.py   (app Flet no celular)
Gerar APK:                 flet build apk
"""

import flet as ft

from rolox import discord_log
from rolox.telas import RoloxApp

discord_log.carregar_env()      # webhooks do Discord em ~/.rolox.env (opcional)


async def main(page: ft.Page) -> None:
    await RoloxApp(page).iniciar()


if __name__ == "__main__":
    ft.run(main)
