"""Rolox — versão Flask (roda no Termux e abre no navegador do celular).

    pip install flask requests
    python app.py            -> abra http://localhost:8550

Só aceita conexões do próprio aparelho (127.0.0.1). Para liberar na rede Wi-Fi,
use ROLOX_HOST=0.0.0.0 (cuidado: qualquer um na rede poderia abrir sua sessão).
"""

from __future__ import annotations

import functools
import ipaddress
import uuid
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import json

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_from_directory,
                   session, url_for)

import avatar as avatar_mod
import discord_log
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader
from markupsafe import Markup
from rolox_api import ErroRolox, RoloxAPI, Sessao
from studio_local import STUDIO_URL as STUDIO_URL_PADRAO, COMANDO_INSTALAR, COMANDO_LIGAR, MODELOS as MODELOS_STUDIO, StudioLocal

IDIOMAS = {"pt-BR": "Português", "en": "English", "es": "Español"}
# O ROLOX Studio (editor) roda dentro do site: páginas e arquivos vêm de Rolox-Studio/
PASTA_STUDIO = Path(os.environ.get("ROLOX_PASTA_STUDIO", Path(__file__).resolve().parents[2] / "Rolox-Studio"))
NOME_PROJETO = __import__("re").compile(r"^[A-Za-z0-9_-]{1,40}$")
TAMANHO_MAX_PROJETO = 5 * 1024 * 1024
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


NO_RENDER = bool(os.environ.get("RENDER"))      # o Render define RENDER=true


def ip_do_visitante() -> Optional[str]:
    """IP de quem abriu o site. No Render, vem do cabeçalho do proxy
    (ROLOX_IP_CABECALHO, padrão CF-Connecting-IP); localmente, do próprio socket."""
    nome = os.environ.get("ROLOX_IP_CABECALHO", "CF-Connecting-IP" if NO_RENDER else "")
    if not nome:
        bruto = request.remote_addr or ""
    else:
        partes = [x.strip() for x in request.headers.get(nome, "").split(",") if x.strip()]
        try:
            bruto = partes[int(os.environ.get("ROLOX_IP_POSICAO", "0"))]
        except (IndexError, ValueError):
            return None
    try:
        return str(ipaddress.ip_address(bruto))
    except ValueError:
        return None


def criar_app(fabrica_api: Callable[[Optional[Sessao]], RoloxAPI] = RoloxAPI,
              segredo: Optional[str] = None, studio: Optional[StudioLocal] = None,
              studio_no_navegador: Optional[bool] = None) -> Flask:
    app = Flask(__name__)
    studio_no_site = studio is None and (PASTA_STUDIO / "static" / "studio").is_dir()
    studio = studio or StudioLocal("" if studio_no_site else STUDIO_URL_PADRAO)
    if studio_no_navegador is None:
        studio_no_navegador = False
    app.config.update(
        SECRET_KEY=segredo or _segredo(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SECURE=NO_RENDER or bool(os.environ.get("ROLOX_HTTPS")),
    )
    app.jinja_env.filters["data"] = formatar_data
    app.jinja_loader = ChoiceLoader([app.jinja_loader,
                                     PrefixLoader({"editor": FileSystemLoader(PASTA_STUDIO / "templates")})])

    # ------------------------------------------------------ sessão / API
    @app.before_request
    def preparar():
        g.api = fabrica_api(Sessao.de_dict(session.get("sb")))
        g.api.ip_cliente = ip_do_visitante()
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
                "eh_dono": bool(session.get("dono")) and "sb" in session,
                "desenhar_avatar": lambda a, largura=120: Markup(avatar_mod.svg(a, largura))}

    def carregar_perfil() -> dict:
        """Lê o perfil e lembra na sessão se é ADM (só para mostrar a aba;
        quem decide de verdade é o Supabase em cada ação de ADM)."""
        p = g.api.meu_perfil()
        session["adm"] = bool(p.get("is_adm"))
        try:
            session["dono"] = g.api.eh_dono()
        except ErroRolox:
            session["dono"] = False
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
    @app.get("/saude")
    def saude():
        return "ok"

    if os.environ.get("ROLOX_DEBUG_IP") == "1":     # só para configurar o Render; desligado por padrão
        @app.get("/_ip")
        def ver_ip():
            nomes = ("X-Forwarded-For", "CF-Connecting-IP", "True-Client-IP", "X-Real-IP")
            return jsonify({n: request.headers.get(n) for n in nomes} |
                           {"remote_addr": request.remote_addr, "escolhido": ip_do_visitante()})

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
                                f.get("localizacao") == "on", codigo_dono=f.get("codigo_dono", ""))
            except ErroRolox as e:
                flash(e.mensagem, "erro")
                return render_template("cadastro.html", dados=f, dono=bool(f.get("codigo_dono"))), 400
            try:
                g.api.atualizar_local("menu")
            except ErroRolox:
                pass
            flash("Conta criada! Bem-vindo ao Rolox.", "ok")
            return redirect(url_for("inicio"))
        return render_template("cadastro.html", dados={}, dono=request.args.get("dono") == "1")

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
        return redirect(url_for("jogos" if request.form.get("voltar") == "jogos" else "servidores"))

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

    # ------------------------------------------------------------ Studio
    @app.get("/studio")
    @logado
    def studio_tela():
        """ROLOX Studio: o editor roda neste aparelho (Rolox-Studio/servidor.py, porta 8600)."""
        if studio_no_site:
            projetos = [p | {"tamanho": p.get("tamanho") or 0} for p in g.api.projetos_listar()]
            return render_template("studio.html", studio=studio, ligado=True, no_navegador=False, no_site=True,
                                   projetos=projetos, modelos=MODELOS_STUDIO, comando=COMANDO_LIGAR,
                                   instalar=COMANDO_INSTALAR, aba="studio")
        if studio_no_navegador:
            return render_template("studio.html", studio=studio, ligado=False, no_navegador=True,
                                   projetos=[], modelos=MODELOS_STUDIO, comando=COMANDO_LIGAR,
                                   instalar=COMANDO_INSTALAR, aba="studio")
        ligado = studio.ligado()
        return render_template("studio.html", studio=studio, ligado=ligado, no_navegador=False,
                               projetos=studio.projetos() if ligado else [],
                               modelos=MODELOS_STUDIO, comando=COMANDO_LIGAR,
                               instalar=COMANDO_INSTALAR, aba="studio")

    # ---------------------------------------- Studio dentro do site
    if studio_no_site:
        @app.get("/static/studio/<path:arquivo>")
        def studio_arquivos(arquivo):
            return send_from_directory(PASTA_STUDIO / "static" / "studio", arquivo)

        @app.get("/static/vendor/<path:arquivo>")
        def studio_vendor(arquivo):
            return send_from_directory(PASTA_STUDIO / "static" / "vendor", arquivo)

        @app.get("/studio/<modo>")
        @logado
        def studio_editor(modo):
            if modo not in ("leve", "pc"):
                abort(404)
            return render_template("editor/studio.html", modo="leve" if modo == "leve" else "pesado", site=True)

        @app.get("/aprender/python-no-celular")
        def aprender_python():
            return render_template("editor/em_breve.html", titulo="Python no celular (Termux)")

        @app.get("/api/projetos")
        @logado
        def projetos_listar():
            return jsonify([{"nome": p["nome"], "tamanho": p.get("tamanho") or 0} for p in g.api.projetos_listar()])

        @app.get("/api/projetos/<nome>")
        @logado
        def projeto_abrir(nome):
            if not NOME_PROJETO.match(nome):
                abort(400, "Nome inválido.")
            dados = g.api.projeto_abrir(nome)
            if dados is None:
                abort(404, "Projeto não encontrado.")
            return jsonify(dados)

        @app.put("/api/projetos/<nome>")
        @logado
        def projeto_salvar(nome):
            if not NOME_PROJETO.match(nome):
                abort(400, "Nome inválido: use letras, números, - ou _ (até 40).")
            if not request.is_json:           # JSON obrigatório: outro site não consegue mandar sem permissão (CORS)
                abort(415, "Envie o projeto em JSON.")
            bruto = request.get_data(cache=True)
            if len(bruto) > TAMANHO_MAX_PROJETO:
                abort(413, "Projeto grande demais (máx. 5 MB).")
            dados = request.get_json(silent=True)
            if not isinstance(dados, dict) or dados.get("formato") != "rolox-studio":
                abort(400, "Arquivo não é um projeto do Rolox Studio.")
            g.api.projeto_salvar(nome, dados, len(bruto))
            return jsonify({"ok": True, "nome": nome})

    # ------------------------------------------------ jogos (mapas do bucket)
    def _mapa_ou_404(mapa_id: str) -> dict:
        try:
            uuid.UUID(mapa_id)
        except ValueError:
            abort(404)
        m = g.api.mapa(mapa_id)
        if not m:
            abort(404)
        return m

    @app.get("/jogos")
    @logado
    def jogos():
        carregar_perfil()
        return render_template("jogos.html", publicados=g.api.mapas_publicados(), meus=g.api.meus_mapas(),
                               aba="jogos")

    @app.post("/jogos/<mapa_id>/jogar")
    @logado
    def jogar_entrar(mapa_id: str):
        """Entra num servidor desse jogo com vaga (ou cria um) e abre o jogo com o chat."""
        m = _mapa_ou_404(mapa_id)
        if not m.get("gameid") or not m.get("caminho_aprovado"):
            flash("Esse jogo ainda não foi aprovado pelo dono.", "erro")
            return redirect(url_for("jogos"))
        perfil = g.api.meu_perfil()
        hack = perfil.get("jogo_mod") == m["gameid"]
        livres = [x for x in g.api.servidores() if x["gameid"] == m["gameid"] and x["status"] == "aberto"
                  and x["is_hack_server"] == hack and x["humanos"] < x["capacidade"]]
        if livres:
            uid = max(livres, key=lambda x: x["humanos"])["server_uid"]     # junta a galera
        else:
            uid = g.api.criar_servidor(m["gameid"], 10, hack)["server_uid"]
        r = g.api.entrar(uid)
        if r["resultado"] == "fila":
            flash(f"Servidor cheio. Você está na fila, posição {r['posicao']}.", "ok")
            return redirect(url_for("jogos"))
        return redirect(url_for("jogar", mapa_id=mapa_id, s=uid))

    @app.get("/jogar/<mapa_id>")
    @logado
    def jogar(mapa_id: str):
        m = _mapa_ou_404(mapa_id)
        perfil = carregar_perfil()
        teste = request.args.get("teste") == "1"
        if teste and not (session.get("dono") or m["autor_id"] == g.api.user_id):
            abort(403)
        uid = request.args.get("s") or None
        s = None
        if uid and not teste:
            if g.api.onde_estou()["servidor"] != uid:
                flash("Você não está nesse servidor.", "erro")
                return redirect(url_for("jogos"))
            s = g.api.servidor(uid)
        if not teste and not m.get("caminho_aprovado"):
            abort(404)
        return render_template("jogar.html", m=m, s=s, teste=teste, eu=perfil.get("username", "Jogador"),
                               host=bool(s) and s["host_id"] == g.api.user_id,
                               url_mapa=url_for("mapa_dados", mapa_id=mapa_id, versao="enviada" if teste else "aprovada"))

    @app.get("/api/mapas/<mapa_id>/dados")
    @logado
    def mapa_dados(mapa_id: str):
        m = _mapa_ou_404(mapa_id)
        caminho = m.get("caminho_enviado") if request.args.get("versao") == "enviada" else m.get("caminho_aprovado")
        if not caminho:
            abort(404)
        resp = app.response_class(g.api.baixar_mapa(caminho), mimetype="application/json")
        resp.headers["Cache-Control"] = "private, max-age=60"
        return resp

    @app.post("/api/mapas/enviar")
    @logado
    def mapa_enviar():
        if len(request.get_data(cache=True)) > TAMANHO_MAX_PROJETO:
            raise ErroRolox("mapa_grande")
        d = request.get_json(silent=True) or {}
        projeto = d.get("projeto")
        if not isinstance(projeto, dict) or projeto.get("formato") != "rolox-studio":
            raise ErroRolox("mapa_invalido")
        mapa_id = str(d.get("mapa_id") or "")
        try:
            mapa_id = str(uuid.UUID(mapa_id))
        except ValueError:
            mapa_id = str(uuid.uuid4())
        if (m := g.api.mapa(mapa_id)) and m["autor_id"] != g.api.user_id:
            mapa_id = str(uuid.uuid4())          # id de mapa alheio: vira um mapa novo meu
        conteudo = json.dumps(projeto, ensure_ascii=False, separators=(",", ":")).encode()
        r = g.api.enviar_mapa(mapa_id, str(d.get("nome", "")), str(d.get("descricao", "")), conteudo)
        return jsonify(r)

    # --------------------------------------------------------------- dono
    @app.get("/dono")
    @logado
    def dono():
        carregar_perfil()
        if not session.get("dono"):
            abort(403)
        return render_template("dono.html", analise=g.api.mapas_em_analise(),
                               publicados=g.api.mapas_publicados(), aba="dono")

    @app.post("/dono/<mapa_id>/<acao>")
    @logado
    def dono_acao(mapa_id: str, acao: str):
        m = _mapa_ou_404(mapa_id)
        if acao == "aprovar":
            g.api.dono_aprovar_mapa(mapa_id)
            flash(f"\"{m['nome']}\" aprovado! Já aparece em Jogos.", "ok")
        elif acao == "recusar":
            g.api.dono_recusar_mapa(mapa_id, request.form.get("motivo", ""))
            flash(f"\"{m['nome']}\" recusado.", "ok")
        else:
            abort(404)
        return redirect(url_for("dono"))

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
