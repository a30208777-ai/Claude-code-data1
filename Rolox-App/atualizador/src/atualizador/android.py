"""Coisas que só o Android faz (via pyjnius): instalar o .apk, permissão, atalho na tela inicial.

No PC estas funções não existem (levantam SemAndroid): o app mostra um aviso no lugar.
O Flet guarda a Activity em MAIN_ACTIVITY_HOST_CLASS_NAME.mActivity (serious_python).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

AUTORIDADE = "com.rolox.atualizador.arquivos"     # igual ao [tool.flet.android.provider] do pyproject
LINK_ROLOX = "rolox://abrir?via=atualizador"
LINK_ATALHO = "rolox://abrir?via=atalho"
ID_ATALHO = "abrir_rolox"


class SemAndroid(Exception):
    """Rodando fora do Android (PC/teste)."""


def _jnius():
    try:
        from jnius import autoclass, cast   # type: ignore
    except Exception as e:                  # ImportError no PC; erro de JVM fora do Android
        raise SemAndroid(str(e)) from e
    return autoclass, cast


def _activity():
    autoclass, _ = _jnius()
    host = autoclass(os.environ.get("MAIN_ACTIVITY_HOST_CLASS_NAME", "com.flet.serious_python_android.PythonActivity"))
    act = host.mActivity
    if act is None:
        raise SemAndroid("Activity não encontrada")
    return act


def eh_android() -> bool:
    try:
        _activity()
        return True
    except Exception:
        return False


def pasta_downloads() -> Path:
    """Onde guardar o .apk: cache do app no Android (o FileProvider entrega daqui), temp no PC."""
    try:
        return Path(str(_activity().getCacheDir().getAbsolutePath())) / "rolox"
    except Exception:
        return Path(tempfile.gettempdir()) / "atualizador-rolox"


def _sdk() -> int:
    autoclass, _ = _jnius()
    return int(autoclass("android.os.Build$VERSION").SDK_INT)


def pode_instalar() -> bool:
    """O Android deixa este app instalar outros apps? (Android 8+: 'instalar apps desconhecidos')."""
    act = _activity()
    if _sdk() < 26:
        return True
    return bool(act.getPackageManager().canRequestPackageInstalls())


def pedir_permissao_instalar() -> None:
    """Abre a tela do Android onde o jogador permite o Atualizador instalar apps."""
    autoclass, _ = _jnius()
    act = _activity()
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")
    it = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + act.getPackageName()))
    it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(it)


def instalar_apk(caminho: Path) -> None:
    """Abre o instalador do Android com o .apk baixado (o jogador confirma 'Instalar')."""
    autoclass, _ = _jnius()
    act = _activity()
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    FileProvider = autoclass("androidx.core.content.FileProvider")
    uri = FileProvider.getUriForFile(act, AUTORIDADE, File(str(caminho)))
    it = Intent(Intent.ACTION_VIEW)
    it.setDataAndType(uri, "application/vnd.android.package-archive")
    it.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(it)


def atalho_suportado() -> bool:
    autoclass, cast = _jnius()
    if _sdk() < 26:
        return False
    sm = cast("android.content.pm.ShortcutManager", _activity().getSystemService("shortcut"))
    return bool(sm and sm.isRequestPinShortcutSupported())


def criar_atalho() -> bool:
    """Pede ao Android um atalho 'ROLOX' na tela inicial que abre o ROLOX pelo Atualizador.

    Devolve False se a tela inicial do aparelho não aceita atalhos. O Android mostra a
    confirmação ("Adicionar à tela inicial?") e o jogador decide.
    """
    autoclass, cast = _jnius()
    if _sdk() < 26:
        return False
    act = _activity()
    sm = cast("android.content.pm.ShortcutManager", act.getSystemService("shortcut"))
    if not sm or not sm.isRequestPinShortcutSupported():
        return False
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    Icon = autoclass("android.graphics.drawable.Icon")
    Builder = autoclass("android.content.pm.ShortcutInfo$Builder")
    it = Intent(Intent.ACTION_VIEW, Uri.parse(LINK_ATALHO))
    it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    info = (Builder(act, ID_ATALHO)
            .setShortLabel("ROLOX")
            .setLongLabel("Abrir o ROLOX")
            .setIcon(Icon.createWithResource(act, act.getApplicationInfo().icon))   # a mesma logo
            .setIntent(it)
            .build())
    return bool(sm.requestPinShortcut(info, None))
