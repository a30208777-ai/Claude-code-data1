"""Rolox — versão Flask (roda no Termux e abre no navegador do celular).

    pip install flask requests
    python app.py            -> abra http://localhost:8550

Só aceita conexões do próprio aparelho (127.0.0.1). Para liberar na rede Wi-Fi,
use ROLOX_HOST=0.0.0.0 (cuidado: qualquer um na rede poderia abrir sua sessão).
"""

from __future__ import annotations

import functools
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)

import avatar as avatar_mod
import discord_log
from markupsafe import Markup
from rolox_api import ErroRolox, RoloxAPI, Sessao

IDIOMAS = {"pt-BR": "Português", "en": "English", "es": "Español"}
ARQUIVO_SEGREDO = Path(os.path.expanduser("~/.rolox_flask_segredo"))


def _segredo() -> str:
    if os.environ.get("ROLOX_SEGREDO"):
        return os.environ["ROLOX_SEGREDO"]
    try:
        if ARQUIVO_SEGREDO.exists():
            return ARQUIVO_SEGREDO.read_text().strip()
        valor = secrets.token_hex(32)
        ARQUIVO_SEGREDO.write_text(valor)
        ARQUIVO_SEGREDO.chmod(0o600)
        return valor
    except OSError:
        return secrets.token_hex(32)


def formatar_data(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except (ValueError, AttributeError):
        return iso or ""


def criar_app(fabrica_api: Callable[[Optional[Sessao]], RoloxAPI] = RoloxAPI,
              segredo: Optional[str] = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=segredo or _segredo(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )
    app.jinja_env.filters["data"] = formatar_data

    # ------------------------------------------------------ sessão / API
    @app.before_request
    def preparar():
        g.api = fabrica_api(Sessao.de_dict(session.get("sb")))
        session.permanent = True
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        if request.method == "POST":
            enviado = request.form.get("csrf") or request.headers.get("X-CSRF")
            if not enviado or not secrets.compare_digest(enviado, session["csrf"]):
                abort(400, "token CSRF inválido — recarregue a página")

    @app.after_request
    def guardar_sessao(resp):
        api = g.get("api")
        if api is not None:
            novo = api.sessao.para_dict() if api.sessao else None
            if novo != session.get("sb"):
                if novo:
                    session["sb"] = novo
                else:
                    session.pop("sb", None)
        return resp

    @app.context_processor
    def globais():
        return {"csrf": session.get("csrf", ""), "logado": "sb" in session,
                "eh_adm": bool(session.get("adm")) and "sb" in session,
                "desenhar_avatar": lambda a, largura=120: Markup(avatar_mod.svg(a, largura))}

    def carregar_perfil() -> dict:
        """Lê o perfil e lembra na sessão se é ADM (só para mostrar a aba;
        quem decide de verdade é o Supabase em cada ação de ADM)."""
        p = g.api.meu_perfil()
        session["adm"] = bool(p.get("is_adm"))
        return p

    @app.errorhandler(ErroRolox)
    def erro_rolox(e: ErroRolox):
        expirou = e.codigo == "sessao_expirada"
        if expirou:
            g.api.sessao = None
        if request.path.startswith("/api/"):
            return jsonify({"erro": e.codigo, "mensagem": e.mensagem}), 401 if expirou else 400
        if expirou:
            flash(e.mensagem, "erro")
            return redirect(url_for("login"))
        if request.method == "GET":       # redirecionar aqui poderia entrar em loop
            return render_template("erro.html", mensagem=e.mensagem), 503 if e.codigo == "sem_conexao" else 400
        flash(e.mensagem, "erro")
        destino = request.referrer if request.referrer and request.referrer.startswith(request.host_url) else None
        return redirect(destino or url_for("inicio"))

    def logado(f):
        @functools.wraps(f)
        def interna(*a, **kw):
            if not g.api.sessao:
                if request.path.startswith("/api/"):
                    return jsonify({"erro": "sessao_expirada"}), 401
                return redirect(url_for("login"))
            return f(*a, **kw)
        return interna

    def nomes_jogos() -> dict:
        return {j["gameid"]: j["nome"] for j in g.api.jogos()}

    # ------------------------------------------------------------ conta
    @app.get("/")
    def raiz():
        return redirect(url_for("inicio" if g.api.sessao else "login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            usuario = request.form.get("usuario", "")
            try:
                g.api.login(usuario, request.form.get("senha", ""))
            except ErroRolox as e:
                if e.codigo == "sessao_expirada":
                    raise
                flash(e.mensagem, "erro")
                return render_template("login.html", usuario=usuario), 401
            try:
                g.api.atualizar_local("menu")
            except ErroRolox:
                pass
            return redirect(url_for("inicio"))
        return render_template("login.html", usuario="")

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            f = request.form
            try:
                g.api.cadastrar(f.get("usuario", ""), f.get("senha", ""),
                                f.get("localizacao") == "on")
            except ErroRolox as e:
                flash(e.mensagem, "erro")
                return render_template("cadastro.html", dados=f), 400
            try:
                g.api.atualizar_local("menu")
            except ErroRolox:
                pass
            flash("Conta criada! Bem-vindo ao Rolox.", "ok")
            return redirect(url_for("inicio"))
        return render_template("cadastro.html", dados={})

    @app.post("/sair-da-conta")
    def sair_da_conta():
        g.api.sair_da_conta()
        flash("Você saiu da conta.", "ok")
        return redirect(url_for("login"))

    # ----------------------------------------------------------- início
    @app.get("/inicio")
    @logado
    def inicio():
        onde = g.api.onde_estou()
        if onde["servidor"]:
            return redirect(url_for("chat", uid=onde["servidor"]))
        presente = g.api.receber_tickets()
        if presente.get("ganhou"):
            flash(f"🎟️ Presente do dia: +{presente['ganhou']} tickets! "
                  f"Amanhã você ganha {presente['amanha']}.", "ok")
        return render_template("inicio.html", perfil=carregar_perfil(), onde=onde,
                               alertas=g.api.alertas(), aba="inicio")

    @app.get("/api/status")
    @logado
    def api_status():
        onde = g.api.onde_estou()
        alertas = g.api.alertas()
        return jsonify({"onde": onde, "alertas": len(alertas),
                        "nao_lidos": sum(1 for a in alertas if not a["lido"])})

    @app.post("/api/alertas/<int:alerta_id>/senha")
    @logado
    def api_ver_senha(alerta_id: int):
        return jsonify({"senha": g.api.ver_senha_tentada(alerta_id)})

    # ------------------------------------------------------- servidores
    @app.get("/servidores")
    @logado
    def servidores():
        perfil = g.api.meu_perfil()
        todos = request.args.get("todos") == "1"
        lista = g.api.servidores()
        if not todos:
            lista = [s for s in lista
                     if (perfil.get("jogo_mod") == s["gameid"]) == s["is_hack_server"]]
        jogos = nomes_jogos()
        return render_template("servidores.html", servidores=lista, jogos=jogos, todos=todos,
                               perfil=perfil, aba="servidores")

    @app.post("/servidores/criar")
    @logado
    def criar_servidor():
        try:
            capacidade = int(request.form.get("capacidade", "0"))
        except ValueError:
            raise ErroRolox("capacidade_invalida")
        s = g.api.criar_servidor(request.form.get("gameid", ""), capacidade,
                                 request.form.get("hack") == "on")
        return _entrar(s["server_uid"])

    @app.post("/servidores/<uid>/entrar")
    @logado
    def entrar(uid: str):
        return _entrar(uid)

    def _entrar(uid: str):
        r = g.api.entrar(uid)
        if r["resultado"] == "fila":
            flash(f"Servidor cheio. Você está na fila, posição {r['posicao']}.", "ok")
            return redirect(url_for("inicio"))
        return redirect(url_for("chat", uid=uid))

    # ------------------------------------------------------------- chat
    @app.get("/chat/<uid>")
    @logado
    def chat(uid: str):
        if g.api.onde_estou()["servidor"] != uid:
            flash("Você não está nesse servidor.", "erro")
            return redirect(url_for("servidores"))
        s = g.api.servidor(uid)
        if not s:
            flash("Esse servidor não existe mais.", "erro")
            return redirect(url_for("servidores"))
        return render_template("chat.html", s=s, jogo=nomes_jogos().get(s["gameid"], s["gameid"]),
                               host=s["host_id"] == g.api.user_id)

    @app.post("/chat/<uid>/sair")
    @logado
    def sair_servidor(uid: str):
        g.api.sair(uid)
        return redirect(url_for("servidores"))

    @app.get("/api/chat/<uid>")
    @logado
    def api_mensagens(uid: str):
        depois = request.args.get("depois", "0")
        novas = g.api.mensagens(uid, int(depois) if depois.isdigit() else 0)
        ainda = g.api.onde_estou()["servidor"] == uid
        return jsonify({"mensagens": novas, "ainda_no_servidor": ainda})

    @app.post("/api/chat/<uid>")
    @logado
    def api_enviar(uid: str):
        dados = request.get_json(silent=True) or {}
        perfil = g.api.meu_perfil()
        return jsonify(g.api.enviar(uid, str(dados.get("texto", "")), perfil.get("idioma")))

    @app.post("/api/heartbeat/<uid>")
    @logado
    def api_heartbeat(uid: str):
        g.api.heartbeat(uid)
        return jsonify({"ok": True})

    # ----------------------------------------------------------- perfil
    @app.route("/perfil", methods=["GET", "POST"])
    @logado
    def perfil():
        if request.method == "POST":
            f = request.form
            idioma = f.get("idioma") if f.get("idioma") in IDIOMAS else "pt-BR"
            g.api.atualizar_perfil(idioma=idioma, jogo_mod=f.get("jogo_mod") or None,
                                   aceitou_localizacao=f.get("localizacao") == "on",
                                   email=f.get("email", ""),
                                   avatar={k: f.get(k, "") for k in avatar_mod.PADRAO})
            g.api.atualizar_local("menu")
            flash("Perfil salvo.", "ok")
            return redirect(url_for("perfil"))
        perfil = carregar_perfil()
        return render_template("perfil.html", perfil=perfil, jogos=nomes_jogos(), idiomas=IDIOMAS,
                               av=avatar_mod, avatar=avatar_mod.normalizar(perfil.get("avatar")),
                               aba="perfil")

    @app.get("/avatar.svg")
    def avatar_svg():
        """Prévia ao vivo do editor de avatar."""
        a = avatar_mod.normalizar({k: request.args.get(k, "") for k in avatar_mod.PADRAO})
        return app.response_class(avatar_mod.svg(a, 160), mimetype="image/svg+xml")

    # --------------------------------------------------------------- ADM
    @app.get("/adm")
    @logado
    def adm():
        d = g.api.adm_painel()
        # IPs bloqueados (ex.: 3 senhas erradas) que ainda não foram para o Discord
        if discord_log.configurado()["banimentos"]:
            for i in d["ips_bloqueados"]:
                if i.get("registrado_discord"):
                    continue
                por = "sistema (3 senhas erradas)" if i.get("automatico") else f"{quem_sou()} (ADM)"
                if discord_log.registrar_sync("ip_bloqueado", f"IP {i['ip']} (tentou entrar em {i.get('conta_alvo') or '?'})",
                                              i.get("motivo") or "", por, "Jogo ROLOX"):
                    g.api.adm_marcar_ip_registrado(i["ip"])
        return render_template("adm.html", d=d, eu=g.api.user_id, jogos=nomes_jogos(),
                               discord=discord_log.configurado(), aba="adm")

    def quem_sou() -> str:
        if "nome" not in g:
            g.nome = g.api.meu_perfil().get("username", "ADM")
        return g.nome

    def avisar_discord(tipo: str, alvo: str, motivo: str = "", duracao: Optional[int] = None) -> None:
        if not discord_log.registrar_sync(tipo, alvo, motivo, f"{quem_sou()} (ADM)", "Jogo ROLOX", duracao) \
                and not all(discord_log.configurado().values()):
            flash("Webhooks do Discord não configurados (~/.rolox.env): feito só no jogo.", "erro")

    @app.post("/adm/<acao>")
    @logado
    def adm_acao(acao: str):
        f = request.form
        if acao == "tickets":
            try:
                qtd = int(f.get("quantidade", "0"))
            except ValueError:
                raise ErroRolox("quantidade_invalida")
            g.api.adm_dar_tickets(f["user_id"], qtd)
            flash("Tickets ajustados.", "ok")
        elif acao == "banir":
            g.api.adm_banir(f["user_id"], f.get("motivo", ""))
            avisar_discord("ban", f.get("nome", "?"), f.get("motivo", ""))
            flash("Usuário banido.", "ok")
        elif acao == "desbanir":
            g.api.adm_desbanir(f["user_id"])
            avisar_discord("desban", f.get("nome", "?"), f.get("motivo", ""))
            flash("Usuário desbanido.", "ok")
        elif acao == "sem-chat":
            try:
                minutos = int(f.get("minutos", "60"))
            except ValueError:
                raise ErroRolox("quantidade_invalida")
            g.api.adm_sem_chat(f["user_id"], minutos, f.get("motivo", ""))
            avisar_discord("sem_chat", f.get("nome", "?"), f.get("motivo", ""), minutos)
            flash("Usuário sem chat.", "ok")
        elif acao == "com-chat":
            g.api.adm_com_chat(f["user_id"])
            avisar_discord("com_chat", f.get("nome", "?"), "chat liberado pelo ADM")
            flash("Chat liberado.", "ok")
        elif acao == "definir-adm":
            g.api.adm_definir_adm(f["user_id"], f.get("adm") == "1")
            flash("Permissão de ADM alterada.", "ok")
        elif acao == "desbloquear-ip":
            g.api.adm_desbloquear_ip(f["ip"])
            avisar_discord("ip_desbloqueado", f"IP {f['ip']}", "")
            flash(f"IP {f['ip']} desbloqueado.", "ok")
        elif acao == "encerrar-servidor":
            g.api.adm_encerrar_servidor(f["server_uid"])
            flash("Servidor encerrado.", "ok")
        else:
            abort(404)
        return redirect(url_for("adm"))

    return app


if __name__ == "__main__":
    discord_log.carregar_env()      # webhooks do Discord em ~/.rolox.env (opcional)
    host = os.environ.get("ROLOX_HOST", "127.0.0.1")
    porta = int(os.environ.get("ROLOX_PORTA", "8550"))
    print(f"Rolox rodando: abra http://localhost:{porta} no navegador do celular")
    criar_app().run(host=host, port=porta, threaded=True)
