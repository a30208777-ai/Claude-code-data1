"""⏰ O próprio ROLOX se abre a cada 5 minutos em /api/notdesligar, pelo endereço público,
para o Render grátis não desligar por falta de visitas.

Só liga no Render (ele define RENDER_EXTERNAL_URL). Um arquivo-trava garante uma só
cutucada mesmo com vários workers do gunicorn."""
import os
import threading
import time
import urllib.request

INTERVALO = 5 * 60
_iniciado = False


def _trava(caminho: str) -> bool:
    try:
        fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        return True
    except FileExistsError:
        try:                                             # trava de um processo que já morreu? assume
            pid = int(open(caminho).read() or 0)
            os.kill(pid, 0)
            return False
        except (ValueError, OSError):
            os.remove(caminho)
            return _trava(caminho)


def _laco(url: str):
    while True:
        time.sleep(INTERVALO)
        try:
            urllib.request.urlopen(url, timeout=30).read()
        except Exception:                                # rede caiu: tenta de novo no próximo
            pass


def iniciar(base: str | None = None, trava: str = "/tmp/rolox_acordar.pid") -> bool:
    global _iniciado
    base = base or os.environ.get("RENDER_EXTERNAL_URL")
    if _iniciado or not base or not _trava(trava):
        return False
    _iniciado = True
    threading.Thread(target=_laco, args=(base.rstrip("/") + "/api/notdesligar",), daemon=True, name="acordar").start()
    return True
