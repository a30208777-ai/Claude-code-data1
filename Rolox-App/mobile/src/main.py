"""Rolox Mobile — ponto de entrada.

Rodar no PC para testar:   flet run src/main.py
Rodar no celular (dev):    flet run --android src/main.py   (app Flet no celular)
Gerar APK:                 flet build apk   (ou pelo GitHub: .github/workflows/apk.yml)
"""

import flet as ft

from rolox import discord_log
from rolox.telas import RoloxApp

try:
    discord_log.carregar_env()  # webhooks do Discord em ~/.rolox.env (opcional; no PC/Termux)
except Exception:              # no APK (Android) não há ~/.rolox.env: segue sem webhooks
    pass


async def main(page: ft.Page) -> None:
    await RoloxApp(page).iniciar()


if __name__ == "__main__":
    ft.run(main)
