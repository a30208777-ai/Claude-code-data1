"""Rolox — versão Flask (roda no Termux e abre no navegador do celular).

    pip install flask requests
    python app.py            -> abra http://localhost:8550

Só aceita conexões do próprio aparelho (127.0.0.1). Para liberar na rede Wi-Fi,
use ROLOX_HOST=0.0.0.0 (cuidado: qualquer um na rede poderia abrir sua sessão).
"""

from __future__ import annotations

import functools
import ipaddress
import time
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
import buscar as busca
import curiosidades
import ia_studio
import midias
import internet
import multijogador
import discord_log
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader
from markupsafe import Markup
from rolox_api import MOTIVOS_DENUNCIA, REDES_SOCIAIS, ErroRolox, RoloxAPI, Sessao
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


def marca_app(perfil: dict) -> Optional[str]:
    """Mesma regra do banco (selo_app): ✅ vale 7 dias depois da última verificação do app."""
    st = perfil.get("app_status")
    if st == "modificado":
        return "modificado"
    if st == "oficial":
        try:
            quando = datetime.fromisoformat(str(perfil.get("app_verificado_em")).replace("Z", "+00:00"))
            if datetime.now(quando.tzinfo) - quando < timedelta(days=7):
                return "oficial"
        except ValueError:
            pass
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
    passes = multijogador.Passes(app.config["SECRET_KEY"])
    cache_parceiros: dict = {}             # username -> (é parceiro?, quando) — evita 1 consulta por mensagem

    def parceiros(nomes) -> set:
        """Quais desses nomes são parceiros (selo 🤝). Guarda por 2 min."""
        agora_ = time.monotonic()
        nomes = {n for n in nomes if n}
        faltam = [n for n in nomes if n not in cache_parceiros or agora_ - cache_parceiros[n][1] > 120]
        if faltam:
            try:
                sim = g.api.parceiros_entre(faltam)
            except ErroRolox:
                sim = set()
            for n in faltam:
                cache_parceiros[n] = (n in sim, agora_)
            if len(cache_parceiros) > 5000:
                cache_parceiros.clear()
        return {n for n in nomes if cache_parceiros.get(n, (False, 0))[0]}
    salas = multijogador.Salas()
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

    app.jinja_env.globals["curiosidades"] = curiosidades.CURIOSIDADES

    def selo_app(valor) -> Markup:
        """✅ app oficial · ❌ app modificado · nada = ainda não abriu pelo app."""
        if isinstance(valor, dict):                      # o próprio perfil (vem com status e data)
            valor = marca_app(valor)
        if valor == "oficial":
            return Markup('<span class="selo-app" title="Usa o app oficial do ROLOX">✅</span>')
        if valor == "modificado":
            return Markup('<span class="selo-app" title="Usando app modificado (não oficial)">❌</span>')
        return Markup("")

    @app.context_processor
    def globais():
        return {"csrf": session.get("csrf", ""), "logado": "sb" in session,
                "eh_adm": bool(session.get("adm")) and "sb" in session,
                "eh_dono": bool(session.get("dono")) and "sb" in session,
                "desenhar_avatar": lambda a, largura=120: Markup(avatar_mod.svg(a, largura)),
                "motivos_denuncia": MOTIVOS_DENUNCIA,
                "selo": lambda parceiro: Markup('<span class="selo" title="Parceiro do ROLOX">🤝</span>') if parceiro else "",
                "selo_app": selo_app}

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

    # páginas de erro amigáveis (a API continua respondendo JSON)
    PAGINAS_ERRO = {404: ("🧭", "Página não encontrada", "Esse endereço não existe ou o jogo saiu do ar."),
                    403: ("🔒", "Sem permissão", "Você não pode abrir isso com esta conta."),
                    413: ("📦", "Grande demais", "O arquivo ou os dados enviados passam do limite.")}

    def _pagina_erro(e):
        codigo = getattr(e, "code", 500) or 500
        emoji, titulo, msg = PAGINAS_ERRO.get(codigo, ("⚠️", "Algo deu errado", "Tente de novo daqui a pouco."))
        if request.path.startswith("/api/"):
            return jsonify({"erro": codigo, "mensagem": msg}), codigo
        return render_template("erro.html", emoji_erro=emoji, titulo_erro=titulo, mensagem=msg), codigo

    for _c in PAGINAS_ERRO:
        app.register_error_handler(_c, _pagina_erro)

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

    def destino_do_servidor(uid: str) -> str:
        """Jogo 3D (mapa) -> /jogar com o chat; servidor antigo (só chat) -> /chat."""
        s = g.api.servidor(uid)
        if s:
            m = g.api.mapa_do_jogo(s["gameid"])
            if m:
                return url_for("jogar", mapa_id=m["id"], s=uid)
        return url_for("chat", uid=uid)

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

    # ------------------------------------------- entrar pelo app (APK)
    @app.get("/app/entrar")
    def app_entrar():
        """O app abre /app/entrar#t=<token>&mapa=<id>: o token fica no "#" (não vai para o
        servidor nem para os logs); a página manda por POST e já leva para o jogo."""
        return render_template("app_entrar.html")

    @app.post("/api/app/sessao")
    def app_sessao():
        d = request.get_json(silent=True) or {}
        g.api.entrar_com_token(str(d.get("token", "")))
        perfil = carregar_perfil()
        return jsonify({"username": perfil.get("username", "")})

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
            return redirect(destino_do_servidor(onde["servidor"]))
        presente = g.api.receber_tickets()
        if presente.get("ganhou"):
            flash(f"🎟️ Presente do dia: +{presente['ganhou']} tickets! "
                  f"Amanhã você ganha {presente['amanha']}.", "ok")
        try:
            todos = g.api.meus_amigos()
            pedidos = [a["username"] for a in todos if a["tipo"] == "recebido"]
            amigos = [a for a in todos if a["tipo"] == "amigo" and a.get("online")]
            selo = parceiros(a["username"] for a in amigos)
            for a in amigos:
                a["parceiro"] = a["username"] in selo
        except ErroRolox:
            amigos, pedidos = [], []
        try:
            missoes = g.api.minhas_missoes()
        except ErroRolox:
            missoes = []
        return render_template("inicio.html", perfil=carregar_perfil(), onde=onde, missoes=missoes, pedidos=pedidos,
                               alertas=g.api.alertas(), amigos_online=amigos, aba="inicio")

    @app.post("/missoes/<codigo>/resgatar")
    @logado
    def missao_resgatar(codigo: str):
        r = g.api.resgatar_missao(codigo)                 # o banco confere se foi cumprida
        flash(f"🎯 Missão cumprida! +{r.get('ganhou', 0)} tickets.", "ok")
        return redirect(url_for("inicio") + "#missoes")

    @app.get("/api/status")
    @logado
    def api_status():
        onde = g.api.onde_estou()
        alertas = g.api.alertas()
        return jsonify({"onde": onde, "alertas": len(alertas),
                        "destino": destino_do_servidor(onde["servidor"]) if onde["servidor"] else None,
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
        selo = parceiros(m.get("username") for m in novas if not m.get("bot_id"))
        for m in novas:
            m["parceiro"] = m.get("username") in selo and not m.get("bot_id")
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
        try:
            compras = g.api.minhas_compras()
            comprados: dict = {}
            for i in g.api.loja_itens():
                if i["codigo"] in compras:
                    comprados.setdefault(i["campo"], set()).add(i["valor"])
        except ErroRolox:
            comprados = {}
        return render_template("perfil.html", perfil=perfil, jogos=nomes_jogos(), idiomas=IDIOMAS, comprados=comprados,
                               av=avatar_mod, avatar=avatar_mod.normalizar(perfil.get("avatar")),
                               aba="perfil")

    # ------------------------------------------------ termos e política (públicas)
    @app.get("/termos")
    def termos():
        return render_template("termos.html")

    @app.get("/politica")
    def politica():
        return render_template("politica.html")

    @app.post("/perfil/bio")
    @logado
    def perfil_bio():
        r = g.api.definir_bio(request.form.get("bio", ""))
        flash("✍️ \"Sobre mim\" salvo!" if r.get("bio") else "✍️ \"Sobre mim\" apagado.", "ok")
        return redirect(url_for("perfil") + "#sobre-mim")

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
            perfil = carregar_perfil()
            return render_template("editor/studio.html", modo="leve" if modo == "leve" else "pesado", site=True,
                                   tickets="∞" if perfil.get("is_adm") else perfil.get("tickets", 0),
                                   custo_ia=ia_studio.CUSTO_TICKETS, midias_base=g.api.url_midias())

        @app.post("/api/midias")
        @logado
        def enviar_midia():
            """Studio do site: envia um som ou vídeo do criador para o bucket "midias"."""
            f = request.files.get("arquivo")
            if not f:
                return jsonify({"erro": "sem_arquivo", "mensagem": "Escolha um arquivo."}), 400
            dados = f.read(midias.MAX_VIDEO + 1)
            try:
                info = midias.preparar(dados, g.api.user_id)
            except ValueError as e:
                return jsonify({"erro": "arquivo_invalido", "mensagem": str(e)}), 400
            g.api.enviar_midia(info["midia"], dados, info["content_type"])
            return jsonify({"tipo": info["tipo"], "midia": info["midia"], "url": f"{g.api.url_midias()}/{info['midia']}"})

        @app.post("/api/studio/ia")
        @logado
        def studio_ia():
            """IA do Studio: cobra 10 tickets, pergunta aos modelos e devolve os tickets se ninguém responder."""
            dados = request.get_json(silent=True) or {}
            mensagens = ia_studio.limpar_historico(dados.get("mensagens"))
            cena = str(dados.get("cena") or "")[:ia_studio.MAX_CENA]
            if not mensagens or mensagens[-1]["role"] != "user":
                return jsonify({"erro": "vazio", "mensagem": "Escreva uma pergunta."}), 400
            cobranca = g.api.gastar_tickets_studio_ia()          # erro "tickets insuficientes" vira 400
            modelo, texto = ia_studio.perguntar(mensagens, cena=cena)
            if texto is None:
                saldo = cobranca.get("tickets")
                if cobranca.get("cobranca"):
                    try:
                        saldo = g.api.devolver_tickets_studio_ia(cobranca["cobranca"]).get("tickets", saldo)
                    except ErroRolox:
                        pass
                return jsonify({"erro": "sem_ia", "tickets": saldo,
                                "mensagem": "Nenhuma IA respondeu agora. Seus tickets foram devolvidos. Tente de novo."}), 503
            return jsonify({"resposta": texto, "modelo": modelo, "tickets": cobranca.get("tickets"),
                            "infinito": bool(cobranca.get("infinito"))})

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
        ordem = request.args.get("ordem") if request.args.get("ordem") in ("novos", "curtidos") else "populares"
        try:
            curti = g.api.minhas_curtidas()
        except ErroRolox:
            curti = set()
        return render_template("jogos.html", publicados=g.api.mapas_publicados(ordem), meus=g.api.meus_mapas(),
                               curti=curti, ordem=ordem, aba="jogos")

    @app.get("/ranking")
    @logado
    def ranking():
        """🏅 Criadores com mais sucesso (visitas e curtidas somadas dos jogos aprovados) e jogos mais jogados."""
        carregar_perfil()
        jogos_ = g.api.mapas_publicados("populares")
        criadores: dict = {}
        for m in jogos_:
            c = criadores.setdefault(m["autor_id"], {"visitas": 0, "curtidas": 0, "jogos": 0})
            c["visitas"] += m.get("visitas") or 0
            c["curtidas"] += m.get("curtidas") or 0
            c["jogos"] += 1
        try:
            nomes = g.api.nomes_de(list(criadores))
        except ErroRolox:
            nomes = {}
        lista = sorted(({"nome": nomes.get(k), **v, "pontos": v["visitas"] + 3 * v["curtidas"]}
                        for k, v in criadores.items() if nomes.get(k)),
                       key=lambda x: (-x["pontos"], x["nome"]))[:20]
        return render_template("ranking.html", criadores=lista, jogos=jogos_[:10], aba="jogos")

    @app.get("/jogos/<mapa_id>")
    @logado
    def jogo_pagina(mapa_id: str):
        """Página do jogo: criador, números, recordes, quem está jogando agora e os botões."""
        m = _mapa_ou_404(mapa_id)
        if not m.get("caminho_aprovado") and not (session.get("dono") or m["autor_id"] == g.api.user_id):
            abort(404)
        perfil = carregar_perfil()
        try:
            autor = g.api.nome_de(m["autor_id"])
        except ErroRolox:
            autor = None
        try:
            recordes = g.api.placar(mapa_id)
        except ErroRolox:
            recordes = []
        try:
            servs = [x for x in g.api.servidores() if x.get("gameid") and x["gameid"] == m.get("gameid")]
        except ErroRolox:
            servs = []
        try:
            curti = mapa_id in g.api.minhas_curtidas()
        except ErroRolox:
            curti = False
        uids = {x["server_uid"] for x in servs}
        try:                                            # 👥 amigos jogando este jogo agora
            amigos_aqui = [a for a in g.api.meus_amigos() if a["tipo"] == "amigo" and a.get("server_uid") in uids]
        except ErroRolox:
            amigos_aqui = []
        return render_template("jogo.html", m=m, autor=autor, recordes=recordes, curti=curti, amigos_aqui=amigos_aqui,
                               jogando=sum(x.get("humanos", 0) for x in servs if not x.get("is_hack_server")),
                               jogando_hack=sum(x.get("humanos", 0) for x in servs if x.get("is_hack_server")),
                               servidores=len(servs), eu=perfil.get("username"), aba="jogos")

    @app.get("/api/placar/<mapa_id>")
    @logado
    def placar_ver(mapa_id: str):
        _mapa_ou_404(mapa_id)
        eu = g.api.user_id
        lista = g.api.placar(mapa_id)
        selo = parceiros(x["username"] for x in lista)
        return jsonify([{"pos": i + 1, "nome": x["username"], "estatistica": x["estatistica"],
                         "valor": float(x["valor"]), "eu": x["user_id"] == eu, "parceiro": x["username"] in selo}
                        for i, x in enumerate(lista)])

    @app.post("/api/placar/<mapa_id>")
    @logado
    def placar_enviar(mapa_id: str):
        if (b := _bloqueio_hack(mapa_id)) is not None:
            return b
        d = request.get_json(silent=True) or {}
        try:
            valor = float(d.get("valor"))
        except (TypeError, ValueError):
            abort(400)
        if not (0 <= valor <= 1e12):
            abort(400)
        return jsonify(g.api.registrar_placar(mapa_id, str(d.get("estatistica", "Pontos"))[:32], valor))

    @app.post("/jogos/<mapa_id>/curtir")
    @logado
    def jogo_curtir(mapa_id: str):
        _mapa_ou_404(mapa_id)
        dados = request.get_json(silent=True) or request.form
        r = g.api.curtir_mapa(mapa_id, str(dados.get("curtir", "1")) in ("1", "true", "True"))
        if request.is_json:
            return jsonify(r)
        if request.form.get("voltar") == "jogo":
            return redirect(url_for("jogo_pagina", mapa_id=mapa_id))
        return redirect(url_for("jogos", ordem=request.form.get("ordem") or None) + f"#mapa-{mapa_id}")

    @app.post("/jogos/<mapa_id>/jogar")
    @logado
    def jogar_entrar(mapa_id: str):
        """Entra num servidor desse jogo com vaga (ou cria um) e abre o jogo com o chat."""
        m = _mapa_ou_404(mapa_id)
        if not m.get("gameid") or not m.get("caminho_aprovado"):
            flash("Esse jogo ainda não foi aprovado pelo dono.", "erro")
            return redirect(url_for("jogos"))
        perfil = g.api.meu_perfil()
        try:
            g.api.visitar_mapa(mapa_id)           # conta 1 visita por jogador por dia
        except ErroRolox:
            pass
        return _entrar_servidor(m, hack=perfil.get("jogo_mod") == m["gameid"])

    def _entrar_servidor(m: dict, hack: bool, voltar: str = "jogos"):
        """Junta a galera num servidor com vaga (ou cria). O banco garante: quem usa hack/mod neste
        jogo só entra em servidor hack, e servidor hack só aceita quem usa hack/mod."""
        livres = [x for x in g.api.servidores() if x["gameid"] == m["gameid"] and x["status"] == "aberto"
                  and x["is_hack_server"] == hack and x["humanos"] < x["capacidade"]]
        if livres:
            uid = max(livres, key=lambda x: x["humanos"])["server_uid"]
        else:
            uid = g.api.criar_servidor(m["gameid"], 10, hack)["server_uid"]
        r = g.api.entrar(uid)
        if r["resultado"] == "fila":
            flash(f"Servidor cheio. Você está na fila, posição {r['posicao']}.", "ok")
            return redirect(url_for(voltar))
        return redirect(url_for("jogar", mapa_id=m["id"], s=uid))

    # ---------------------------------------------------------- ROLOX Hacks
    # Servidores de hack/mod: separados dos jogadores do ROLOX (o banco não mistura) e com o
    # executor 🤖 de scripts. No modo hack não vale recorde, Cofre nem emblema.
    @app.get("/hacks")
    @logado
    def hacks():
        perfil = carregar_perfil()
        return render_template("hacks.html", publicados=g.api.mapas_publicados("populares"), perfil=perfil, aba="hacks")

    @app.post("/hacks/<mapa_id>/jogar")
    @logado
    def hacks_jogar(mapa_id: str):
        m = _mapa_ou_404(mapa_id)
        if not m.get("gameid") or not m.get("caminho_aprovado"):
            flash("Esse jogo ainda não foi aprovado pelo dono.", "erro")
            return redirect(url_for("hacks"))
        perfil = carregar_perfil()
        if not session.get("dono") and perfil.get("jogo_mod") != m["gameid"]:
            g.api.atualizar_perfil(jogo_mod=m["gameid"])        # o banco tira você dos servidores normais desse jogo
        # o dono usa os 2 apps normalmente: entra no servidor hack sem sair dos normais
        return _entrar_servidor(m, hack=True, voltar="hacks")

    @app.post("/hacks/sair-do-modo")
    @logado
    def hacks_sair_do_modo():
        g.api.atualizar_perfil(jogo_mod=None)
        flash("Você saiu do modo hack. Agora joga nos servidores normais do ROLOX.", "ok")
        return redirect(url_for("jogos"))

    def _bloqueio_hack(mapa_id: str):
        """No modo hack não vale recorde, Cofre nem emblema (senão o hack vira trapaça no ROLOX normal)."""
        m = _mapa_ou_404(mapa_id)
        if m.get("gameid") and g.api.meu_perfil().get("jogo_mod") == m["gameid"]:
            return jsonify({"erro": "modo_hack", "mensagem": "No modo hack não vale recorde, Cofre nem emblema."}), 403
        return None

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
        avatar = avatar_mod.normalizar(perfil.get("avatar"))
        dono_jogo = bool(session.get("dono"))           # carregar_perfil acabou de conferir no banco
        criador_jogo = m.get("autor_id") == g.api.user_id  # o criador do mapa também tem o painel no jogo dele
        passe = passes.criar(s["server_uid"], g.api.user_id, perfil.get("username", "Jogador"), avatar,
                             parceiro=bool(perfil.get("is_parceiro")), dono=dono_jogo) if s else None
        try:
            curti = mapa_id in g.api.minhas_curtidas()
        except ErroRolox:
            curti = False
        hack = bool(s and s.get("is_hack_server"))
        return render_template("jogar.html", m=m, s=s, teste=teste, eu=perfil.get("username", "Jogador"), curti=curti,
                               hack=hack, dono_jogo=dono_jogo, criador_jogo=criador_jogo and not dono_jogo,
                               midias_base=g.api.url_midias(),
                               avatar=avatar, passe=passe,
                               host=bool(s) and s["host_id"] == g.api.user_id,
                               url_mapa=url_for("mapa_dados", mapa_id=mapa_id, versao="enviada" if teste else "aprovada"))

    # multijogador: posições de quem está no mesmo servidor (sem Supabase a cada quadro)
    def _passe_meu() -> dict:
        d = request.get_json(silent=True) or request.form
        passe = passes.ler(str(d.get("passe", "")))
        if not passe or passe["u"] != g.api.user_id:
            abort(403)
        return passe

    @app.post("/api/sala")
    @logado
    def sala_atualizar():
        passe = _passe_meu()
        estado = request.get_json(silent=True) or {}
        return jsonify(salas.trocar(passe, estado))

    # Poderes do dono no jogo (botão 👑💎): expulsar, banir e anunciar. O banco confere que é o dono.
    @app.post("/api/dono/jogo/<acao>")
    @logado
    def dono_no_jogo(acao: str):
        passe = _passe_meu()
        if acao not in ("expulsar", "banir", "anunciar"):
            abort(404)
        sala = passe["s"]
        eh_dono = g.api.eh_dono()
        if not eh_dono:
            # criador do mapa: kick e anúncio só nos servidores do PRÓPRIO jogo (banir a conta é só do dono)
            srv = g.api.servidor(sala) or {}
            meus = {x.get("gameid") for x in g.api.meus_mapas() if x.get("gameid")}
            if acao == "banir" or not srv.get("gameid") or srv["gameid"] not in meus:
                return jsonify({"erro": "so_dono", "mensagem": "Só o dono do ROLOX pode fazer isso."}), 403
        d = request.get_json(silent=True) or {}
        if acao == "anunciar":
            n = salas.anunciar(sala, str(d.get("texto", "")))
            return jsonify({"ok": True, "viram": n})
        alvo = str(d.get("alvo", ""))
        nomes = salas.jogadores(sala)
        if alvo not in nomes:
            return jsonify({"erro": "nao_esta", "mensagem": "Esse jogador não está mais no servidor."}), 404
        motivo = str(d.get("motivo", "")).strip()[:200]
        if acao == "expulsar":
            if salas.eh_dono_na_sala(sala, alvo):
                return jsonify({"erro": "intocavel", "mensagem": "Ninguém pode expulsar o dono do ROLOX."}), 403
            if eh_dono:
                g.api.dono_expulsar(sala, alvo)             # tira também do servidor no banco
            quem = "pelo dono" if eh_dono else "pelo criador do jogo"
            salas.expulsar(sala, alvo, f"👑 Você foi expulso do servidor {quem}." + (f" Motivo: {motivo}" if motivo else ""))
            return jsonify({"ok": True, "nome": nomes[alvo]})
        r = g.api.dono_banir(alvo, motivo or "banido pelo dono no jogo")     # o banco nunca bane o dono
        salas.expulsar(sala, alvo, "🔨 Sua conta foi banida pelo dono." + (f" Motivo: {motivo}" if motivo else ""),
                       segundos=7 * 86400)
        discord_log.registrar_sync("ban", r.get("username") or nomes[alvo], motivo or "banido pelo dono no jogo",
                                   f"{quem_sou()} (dono)", "Jogo ROLOX")
        return jsonify({"ok": True, "nome": nomes[alvo]})

    @app.post("/api/sala/sair")
    @logado
    def sala_sair():
        salas.sair(_passe_meu())
        return ("", 204)

    # Cofre: dados salvos do jogador em cada jogo
    @app.get("/api/cofre/<mapa_id>")
    @logado
    def cofre_ler(mapa_id: str):
        _mapa_ou_404(mapa_id)
        return jsonify(g.api.cofre_ler(mapa_id))

    @app.post("/api/cofre/<mapa_id>")
    @logado
    def cofre_salvar(mapa_id: str):
        if len(request.get_data(cache=True)) > 64 * 1024:
            abort(413)
        if (b := _bloqueio_hack(mapa_id)) is not None:
            return b
        dados = (request.get_json(silent=True) or {}).get("dados")
        if not isinstance(dados, dict) or len(dados) > 50:
            abort(400)
        g.api.cofre_salvar(mapa_id, dados)
        return jsonify({"ok": True})

    # Emblemas: os que eu já tenho neste jogo / ganhar um novo
    @app.get("/api/emblemas/<mapa_id>")
    @logado
    def emblemas_meus(mapa_id: str):
        _mapa_ou_404(mapa_id)
        return jsonify(g.api.meus_emblemas(mapa_id))

    @app.post("/api/emblemas/<mapa_id>")
    @logado
    def emblema_ganhar(mapa_id: str):
        if (b := _bloqueio_hack(mapa_id)) is not None:
            return b
        d = request.get_json(silent=True) or {}
        return jsonify(g.api.dar_emblema(mapa_id, str(d.get("codigo", ""))[:30], str(d.get("nome", "")),
                                         str(d.get("emoji", "🏅"))))

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

    # ------------------------------------------------------------ amigos
    @app.get("/amigos")
    @logado
    def amigos():
        carregar_perfil()
        lista = g.api.meus_amigos()
        selo = parceiros(a["username"] for a in lista)
        for a in lista:
            a["parceiro"] = a["username"] in selo
        return render_template("amigos.html", amigos=[a for a in lista if a["tipo"] == "amigo"],
                               recebidos=[a for a in lista if a["tipo"] == "recebido"],
                               enviados=[a for a in lista if a["tipo"] == "enviado"], aba="inicio")

    @app.post("/amigos/pedir")
    @logado
    def amigos_pedir():
        nome = request.form.get("usuario", "").strip().lower()
        r = g.api.pedir_amizade(nome)
        flash(f"Agora você e {nome} são amigos! 🎉" if r.get("status") == "aceita"
              else f"Pedido de amizade enviado para {nome}.", "ok")
        return redirect(url_for("amigos"))

    @app.post("/amigos/<outro>/<acao>")
    @logado
    def amigos_acao(outro: str, acao: str):
        try:
            uuid.UUID(outro)
        except ValueError:
            abort(404)
        if acao in ("aceitar", "recusar"):
            g.api.responder_amizade(outro, acao == "aceitar")
            flash("Pedido aceito! 🎉" if acao == "aceitar" else "Pedido recusado.", "ok")
        elif acao == "desfazer":
            g.api.desfazer_amizade(outro)
            flash("Amizade desfeita.", "ok")
        else:
            abort(404)
        return redirect(url_for("amigos"))

    @app.post("/amigos/entrar/<uid>")
    @logado
    def amigos_entrar(uid: str):
        """Entrar junto: vai para o mesmo servidor do amigo (se tiver vaga, senão fila)."""
        if not any(a.get("server_uid") == uid for a in g.api.meus_amigos() if a["tipo"] == "amigo"):
            flash("Esse amigo não está mais nesse servidor.", "erro")
            return redirect(url_for("amigos"))
        r = g.api.entrar(uid)
        if r["resultado"] == "fila":
            flash(f"Servidor cheio. Você está na fila, posição {r['posicao']}.", "ok")
            return redirect(url_for("inicio"))
        return redirect(destino_do_servidor(uid))

    # ------------------------------------------------------------ buscar
    @app.get("/buscar")
    @logado
    def buscar():
        q = request.args.get("q", "")[:60]
        tipo = request.args.get("tipo", "todos")
        if tipo not in ("todos", "jogadores", "jogos", "itens", "internet"):
            tipo = "todos"
        if tipo == "internet":
            erro, web = None, []
            if q.strip():
                try:
                    web = internet.pesquisar(q, usuario=g.api.user_id)
                except internet.ErroInternet as e:
                    erro = e.mensagem
            return render_template("buscar.html", q=q, tipo=tipo, termo="", web=web, erro_web=erro,
                                   jogadores=[], jogos=[], itens=[], niveis=busca.NIVEIS, curto=False, aba="buscar")
        termo = busca.termo_valido(q)
        jogadores = jogos = itens = []
        if termo:
            n = 30 if tipo != "todos" else 8
            if tipo in ("todos", "jogadores"):
                jogadores = g.api.buscar_jogadores(termo, n)
            if tipo in ("todos", "jogos"):
                jogos = g.api.buscar_jogos(termo, n)
            if tipo in ("todos", "itens"):
                itens = busca.buscar_itens(termo, n)
        return render_template("buscar.html", q=q, tipo=tipo, termo=termo, jogadores=jogadores, jogos=jogos,
                               itens=itens, niveis=busca.NIVEIS, curto=bool(q.strip()) and not termo, aba="buscar")

    @app.get("/api/internet")
    @logado
    def api_internet():
        """Pesquisa na internet (fontes seguras) feita pelo servidor — para jogos e jogadores."""
        try:
            r = internet.pesquisar(request.args.get("q", ""), usuario=g.api.user_id)
        except internet.ErroInternet as e:
            return jsonify({"erro": e.codigo, "mensagem": e.mensagem}), 429 if e.codigo == "muitas_pesquisas" else 400
        return jsonify({"resultados": r, "texto": internet.como_texto(r)})

    @app.post("/buscar/usar-item")
    @logado
    def buscar_usar_item():
        campo, valor = request.form.get("campo", ""), request.form.get("valor", "")
        if not busca.item_valido(campo, valor):
            abort(400)
        atual = avatar_mod.normalizar(carregar_perfil().get("avatar"))
        atual[campo] = valor
        g.api.atualizar_perfil(avatar=atual)
        flash("Item colocado no seu avatar! 👕", "ok")
        return redirect(url_for("buscar", q=request.form.get("q", ""), tipo=request.form.get("tipo", "itens")))

    # --------------------------------------------------------- denúncias
    def _registrar_denuncia(dados) -> dict:
        tipo, alvo = str(dados.get("tipo", "")), str(dados.get("alvo", ""))
        motivo, detalhe = str(dados.get("motivo", "")), str(dados.get("detalhe", ""))
        r = g.api.denunciar(tipo, alvo, motivo, detalhe)
        if not r.get("repetida"):
            nome = r.get("alvo_nome") or alvo
            discord_log.registrar_sync("denuncia", f"{'🎮 jogo' if tipo == 'jogo' else '👤'} {nome}",
                                       f"{MOTIVOS_DENUNCIA.get(motivo, motivo)}{(': ' + detalhe[:300]) if detalhe else ''}",
                                       quem_sou(), "Site ROLOX")
        return r

    def denuncias_abertas() -> list[dict]:
        try:
            return g.api.adm_denuncias()
        except ErroRolox:
            return []                      # a fila não derruba o painel

    @app.post("/denunciar")
    @logado
    def denunciar():
        _registrar_denuncia(request.form)
        flash("🚩 Denúncia enviada. Obrigado! A moderação vai olhar.", "ok")
        voltar = request.form.get("voltar", "")
        return redirect(voltar if voltar.startswith("/") and not voltar.startswith("//") else url_for("inicio"))

    @app.post("/api/denunciar")
    @logado
    def api_denunciar():
        r = _registrar_denuncia(request.get_json(silent=True) or {})
        return jsonify({"ok": True, "repetida": bool(r.get("repetida"))})

    @app.post("/moderacao/denuncias/<int:denuncia_id>/<acao>")
    @logado
    def resolver_denuncia(denuncia_id: int, acao: str):
        if acao not in ("resolvida", "descartada"):
            abort(404)
        g.api.adm_resolver_denuncia(denuncia_id, acao, request.form.get("nota", ""))
        flash("Denúncia " + ("resolvida." if acao == "resolvida" else "descartada."), "ok")
        voltar = request.form.get("voltar", "")
        return redirect(voltar if voltar in ("/adm", "/dono") else url_for("inicio"))

    # -------------------------------------------------------------- loja
    @app.get("/loja")
    @logado
    def loja():
        perfil = carregar_perfil()
        try:
            compras = g.api.minhas_compras()
        except ErroRolox:
            compras = set()
        return render_template("loja.html", perfil=perfil, itens=g.api.loja_itens(), compras=compras,
                               avatar=avatar_mod.normalizar(perfil.get("avatar")), aba="perfil")

    @app.post("/loja/<codigo>/<acao>")
    @logado
    def loja_acao(codigo: str, acao: str):
        item = {i["codigo"]: i for i in g.api.loja_itens()}.get(codigo)
        if not item or acao not in ("comprar", "usar"):
            abort(404)
        if acao == "comprar":
            r = g.api.comprar_item(codigo)
            flash("Você já tinha esse item." if r.get("ja_tinha") else f"🛒 Comprou {item['nome']}! Já está no seu avatar.", "ok")
        avatar = avatar_mod.normalizar(carregar_perfil().get("avatar"))
        avatar[item["campo"]] = item["valor"]
        g.api.atualizar_perfil(avatar=avatar)            # o banco recusa se não foi comprado
        if acao == "usar":
            flash(f"Usando {item['nome']}.", "ok")
        return redirect(url_for("loja") + f"#item-{codigo}")

    # ---------------------------------------------------------- parceria
    @app.route("/parceria", methods=["GET", "POST"])
    @logado
    def parceria():
        if request.method == "POST":
            r = g.api.usar_chave_parceria(request.form.get("chave", ""))
            flash(f"🤝 Parceria ativada{(' — ' + r['apelido']) if r.get('apelido') else ''}! Bem-vindo, parceiro.", "ok")
            return redirect(url_for("parceria"))
        return render_template("parceria.html", perfil=carregar_perfil(), redes_info=REDES_SOCIAIS, aba="parceria")

    @app.post("/parceria/redes")
    @logado
    def parceria_redes():
        g.api.definir_redes({k: request.form.get(k, "") for k in REDES_SOCIAIS})
        flash("Redes sociais salvas! Elas aparecem na sua página de jogador.", "ok")
        return redirect(url_for("parceria"))

    @app.get("/jogador/<nome>")
    @logado
    def jogador(nome: str):
        p = g.api.perfil_publico(nome)
        if not p:
            abort(404)
        redes = [(k, *REDES_SOCIAIS[k], url) for k, url in (p.get("redes") or {}).items()
                 if k in REDES_SOCIAIS and isinstance(url, str) and url.startswith("https://")]
        try:
            emblemas = g.api.emblemas_de(p["username"])
        except ErroRolox:
            emblemas = []
        por_jogo: dict = {}
        for e in emblemas:
            por_jogo.setdefault(e["jogo"], []).append(e)
        try:                                            # 🎮 jogos aprovados que essa pessoa criou
            publicados = g.api.mapas_publicados("populares")
            nomes = g.api.nomes_de([m["autor_id"] for m in publicados])
            criados = [m for m in publicados if nomes.get(m["autor_id"]) == p["username"]]
        except ErroRolox:
            criados = []
        return render_template("jogador.html", p=p, redes=redes, eu_nome=carregar_perfil().get("username"),
                               emblemas=por_jogo, total_emblemas=len(emblemas), criados=criados,
                               visitas_criados=sum(m.get("visitas") or 0 for m in criados), aba="inicio")

    @app.post("/dono/parcerias/criar")
    @logado
    def dono_parceria_criar():
        r = g.api.dono_criar_chave_parceria(request.form.get("apelido", ""))
        # a chave aparece UMA vez (no banco fica só o hash); não vai para flash/cookie
        return render_template("dono.html", analise=g.api.mapas_em_analise(), publicados=g.api.mapas_publicados(),
                               parcerias=g.api.dono_parcerias(), chave_nova=r, denuncias=denuncias_abertas(),
                               app_oficial=dados_app_oficial(), aba="dono")

    def dados_app_oficial() -> dict:
        try:
            return g.api.dono_chaves_app()
        except ErroRolox:
            return {}

    @app.post("/dono/app/chaves")
    @logado
    def dono_chave_app_adicionar():
        r = g.api.dono_adicionar_chave_app(request.form.get("chave", ""), request.form.get("apelido", ""))
        flash(f"✅ Chave do app cadastrada ({r.get('apelido', '')}). Quem abrir o app oficial fica ✅.", "ok")
        return redirect(url_for("dono") + "#app-oficial")

    @app.post("/dono/app/chaves/<int:chave_id>/revogar")
    @logado
    def dono_chave_app_revogar(chave_id: int):
        g.api.dono_revogar_chave_app(chave_id)
        flash("Chave do app revogada. Apps com essa chave passam a ficar ❌.", "ok")
        return redirect(url_for("dono") + "#app-oficial")

    @app.post("/dono/parcerias/<int:chave_id>/revogar")
    @logado
    def dono_parceria_revogar(chave_id: int):
        g.api.dono_revogar_parceria(chave_id)
        flash("Chave revogada.", "ok")
        return redirect(url_for("dono") + "#parcerias")

    # --------------------------------------------------------------- dono
    @app.get("/dono")
    @logado
    def dono():
        carregar_perfil()
        if not session.get("dono"):
            abort(403)
        return render_template("dono.html", analise=g.api.mapas_em_analise(),
                               publicados=g.api.mapas_publicados(), parcerias=g.api.dono_parcerias(),
                               denuncias=denuncias_abertas(), app_oficial=dados_app_oficial(), aba="dono")

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
        return render_template("adm.html", d=d, eu=g.api.user_id, jogos=nomes_jogos(), denuncias=denuncias_abertas(),
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
