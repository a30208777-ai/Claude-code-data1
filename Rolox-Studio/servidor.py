"""Rolox Studio — servidor local (PC ou Termux).

    pip install -r requirements.txt
    python servidor.py              -> abra http://localhost:8600

Páginas:
    /studio/leve   Studio leve (celular)
    /studio/pc     Studio pesado (PC)
    /controle      controle do PCtoCelular (o celular abre esta página)

Segurança: o Studio, os projetos e o painel do PCtoCelular só respondem ao
próprio aparelho (127.0.0.1). Só a página /controle aceita outros aparelhos,
e mesmo assim precisa do código de 4 dígitos mostrado no Studio do PC.
Para aceitar celulares por Bluetooth, rode com ROLOX_HOST=0.0.0.0.
"""

from __future__ import annotations

import functools
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request
from flask_sock import Sock

PASTA = Path(__file__).resolve().parent
NOME_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
TAMANHO_MAX_PROJETO = 40 * 1024 * 1024
LIMITES = {"bluetooth": 5, "cabo": 2}

# Sites do ROLOX que podem LER a lista de projetos deste Studio (só GET /api/projetos),
# para a aba Studio do site mostrar "ligado" e os projetos. Mais sites: ROLOX_STUDIO_ORIGENS=a,b
ORIGENS_PADRAO = ("https://rolox.onrender.com",)


def origens_permitidas() -> set[str]:
    extras = os.environ.get("ROLOX_STUDIO_ORIGENS", "")
    return set(ORIGENS_PADRAO) | {o.strip().rstrip("/") for o in extras.split(",") if o.strip()}


def eh_local(endereco: str | None) -> bool:
    try:
        return ipaddress.ip_address((endereco or "").split("%")[0]).is_loopback
    except ValueError:
        return False


def via_da_conexao(endereco: str | None) -> str:
    """Cabo: 'adb reverse' chega como 127.0.0.1; ancoragem USB do Android usa 192.168.42.x.
    O resto (ancoragem Bluetooth, normalmente 192.168.44.x) conta como Bluetooth."""
    if eh_local(endereco):
        return "cabo"
    try:
        if ipaddress.ip_address(endereco or "") in ipaddress.ip_network("192.168.42.0/24"):
            return "cabo"
    except ValueError:
        pass
    return "bluetooth"


def ips_locais() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


class CentralPCtoCelular:
    """Liga os celulares (controle) à página do Studio no PC (host). Só memória."""

    def __init__(self, limites: dict | None = None):
        self.limites = dict(limites or LIMITES)
        self.trava = threading.Lock()
        self.host = None
        self.codigo: str | None = None
        self.celulares: dict[str, dict] = {}

    def _enviar(self, ws, msg: dict) -> None:
        try:
            ws.send(json.dumps(msg))
        except Exception:   # conexão caiu
            pass

    def novo_host(self, ws) -> str:
        with self.trava:
            antigo = self.host
            self.host = ws
            self.codigo = f"{secrets.randbelow(10000):04d}"
            celulares = list(self.celulares.values())
            self.celulares.clear()
        if antigo is not None:
            self._enviar(antigo, {"tipo": "substituido"})
        for c in celulares:
            self._enviar(c["ws"], {"tipo": "erro", "mensagem": "O Studio do PC foi reaberto. Conecte de novo."})
        return self.codigo

    def host_saiu(self, ws) -> None:
        with self.trava:
            if self.host is not ws:
                return
            self.host, self.codigo = None, None
            celulares = list(self.celulares.values())
            self.celulares.clear()
        for c in celulares:
            self._enviar(c["ws"], {"tipo": "erro", "mensagem": "O Studio do PC foi fechado."})

    def entrar(self, ws, codigo: str, via: str, nome: str) -> tuple[str | None, str | None]:
        """Devolve (id, None) ou (None, mensagem de erro)."""
        with self.trava:
            if self.host is None or self.codigo is None:
                return None, "O Studio do PC não está aberto (abra /studio/pc no PC)."
            if not secrets.compare_digest(str(codigo), self.codigo):
                return None, "Código errado. Veja o código no painel PCtoCelular do PC."
            usados = sum(1 for c in self.celulares.values() if c["via"] == via)
            if usados >= self.limites.get(via, 0):
                return None, f"Limite atingido: no máximo {self.limites[via]} celulares por {via}."
            ident = secrets.token_hex(4)
            nome = (re.sub(r"[^\w \-]", "", nome or "")[:20].strip() or f"Celular {len(self.celulares) + 1}")
            self.celulares[ident] = {"ws": ws, "via": via, "nome": nome}
            host = self.host
        self._enviar(host, {"tipo": "entrou", "id": ident, "nome": nome, "via": via})
        return ident, None

    def dados(self, ident: str, msg: dict) -> None:
        with self.trava:
            host = self.host if ident in self.celulares else None
        if host is None:
            return
        limpo = {"tipo": "dados", "id": ident,
                 "x": _num(msg.get("x")), "z": _num(msg.get("z")), "pular": bool(msg.get("pular")),
                 "modo": "sensor" if msg.get("modo") == "sensor" else "joystick"}
        s = msg.get("sensor")
        if isinstance(s, dict):
            limpo["sensor"] = {k: _num(s.get(k), 400) for k in ("alpha", "beta", "gamma", "altura")}
        self._enviar(host, limpo)

    def sair(self, ident: str) -> None:
        with self.trava:
            c = self.celulares.pop(ident, None)
            host = self.host
        if c and host is not None:
            self._enviar(host, {"tipo": "saiu", "id": ident})


def _num(v, limite: float = 1.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f:   # NaN
        return 0.0
    return max(-limite, min(limite, f))


def criar_app(pasta_projetos: Path | None = None) -> Flask:
    app = Flask(__name__, template_folder=str(PASTA / "templates"), static_folder=str(PASTA / "static"))
    app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAX_PROJETO
    sock = Sock(app)
    central = CentralPCtoCelular()
    app.extensions["pctocelular"] = central
    projetos = Path(pasta_projetos or os.environ.get("ROLOX_PROJETOS", PASTA / "projetos"))
    projetos.mkdir(parents=True, exist_ok=True)

    def apenas_este_aparelho(f):
        @functools.wraps(f)
        def interna(*a, **kw):
            if not eh_local(request.remote_addr):
                abort(403, "O Studio só pode ser aberto no próprio aparelho.")
            return f(*a, **kw)
        return interna

    @app.after_request
    def cabecalhos(resp):
        origem = request.headers.get("Origin", "")
        if request.path == "/api/projetos" and request.method in ("GET", "OPTIONS") \
                and origem in origens_permitidas():
            resp.headers["Access-Control-Allow-Origin"] = origem
            resp.headers["Access-Control-Allow-Methods"] = "GET"
            if request.headers.get("Access-Control-Request-Private-Network") == "true":
                resp.headers["Access-Control-Allow-Private-Network"] = "true"
        resp.headers.add("Vary", "Origin")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    # ------------------------------------------------------------ páginas
    @app.get("/")
    @apenas_este_aparelho
    def inicio():
        return render_template("inicio.html")

    @app.get("/studio/<modo>")
    @apenas_este_aparelho
    def studio(modo):
        if modo not in ("leve", "pc"):
            abort(404)
        return render_template("studio.html", modo="leve" if modo == "leve" else "pesado")

    @app.get("/controle")
    def controle():
        return render_template("controle.html")

    @app.get("/aprender/python-no-celular")
    def aprender_python():
        return render_template("em_breve.html", titulo="Python no celular (Termux)")

    # ----------------------------------------------------------- projetos
    @app.get("/api/projetos")
    @apenas_este_aparelho
    def listar():
        itens = sorted(projetos.glob("*.rolox.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonify([{"nome": p.name[: -len(".rolox.json")], "tamanho": p.stat().st_size} for p in itens])

    def caminho(nome: str) -> Path:
        if not NOME_VALIDO.match(nome):
            abort(400, "Nome inválido: use letras, números, - ou _ (até 40).")
        return projetos / f"{nome}.rolox.json"

    @app.get("/api/projetos/<nome>")
    @apenas_este_aparelho
    def abrir(nome):
        p = caminho(nome)
        if not p.exists():
            abort(404, "Projeto não encontrado.")
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.put("/api/projetos/<nome>")
    @apenas_este_aparelho
    def salvar(nome):
        p = caminho(nome)
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or dados.get("formato") != "rolox-studio":
            abort(400, "Arquivo não é um projeto do Rolox Studio.")
        temp = p.with_suffix(".tmp")
        temp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        temp.replace(p)
        return jsonify({"ok": True, "nome": nome})

    # ------------------------------------------------------- PCtoCelular
    @sock.route("/ws/pc2cel/host")
    def ws_host(ws):
        if not eh_local(request.remote_addr):
            ws.close(reason=1008, message="só no próprio PC")
            return
        codigo = central.novo_host(ws)
        porta = request.host.rsplit(":", 1)[-1] if ":" in request.host else "80"
        aceita_bt = os.environ.get("ROLOX_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost")
        ws.send(json.dumps({
            "tipo": "codigo", "codigo": codigo, "limites": central.limites, "aceita_bluetooth": aceita_bt,
            "urls": [f"http://localhost:{porta}/controle"] + [f"http://{ip}:{porta}/controle" for ip in ips_locais()],
        }))
        try:
            while ws.receive() is not None:
                pass
        finally:
            central.host_saiu(ws)

    @sock.route("/ws/pc2cel/controle")
    def ws_controle(ws):
        ident = None
        try:
            primeira = json.loads(ws.receive(timeout=30) or "{}")
            via = via_da_conexao(request.remote_addr)
            ident, erro = central.entrar(ws, str(primeira.get("codigo", "")), via, str(primeira.get("nome", "")))
            if erro:
                ws.send(json.dumps({"tipo": "erro", "mensagem": erro}))
                return
            ws.send(json.dumps({"tipo": "ok", "id": ident, "via": via}))
            while True:
                bruto = ws.receive()
                if bruto is None:
                    break
                try:
                    msg = json.loads(bruto)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    central.dados(ident, msg)
        except Exception:
            pass
        finally:
            if ident:
                central.sair(ident)

    return app


if __name__ == "__main__":
    host = os.environ.get("ROLOX_HOST", "127.0.0.1")
    porta = int(os.environ.get("ROLOX_PORTA", "8600"))
    print(f"Rolox Studio: abra http://localhost:{porta}")
    if host != "127.0.0.1":
        print("Aceitando celulares na rede local (PCtoCelular por Bluetooth). O Studio continua só neste aparelho.")
    criar_app().run(host=host, port=porta, threaded=True)
