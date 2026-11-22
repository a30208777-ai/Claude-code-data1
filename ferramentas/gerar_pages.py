"""Gera a versão estática do ROLOX para o GitHub Pages.

O que vai para o Pages (não precisa de servidor):
  • página inicial, Termos, Política e Novidades
  • o ROLOX Studio inteiro (Three.js + Lua + Python rodam no navegador)
O que continua no Render (precisa do servidor Flask + Supabase):
  • login, jogos online, chat, loja, multiplayer, IA do Studio  → links apontam para SITE_RENDER.

Uso:  python ferramentas/gerar_pages.py <pasta_saida>
"""
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SITE_RENDER = "https://rolox-gj2i.onrender.com"
LOCAIS = {"/termos": "termos/", "/politica": "politica/", "/novidades": "novidades/"}


def _relativo(html: str, pre: str) -> str:
    html = re.sub(r'(["\'(`])/static/', lambda m: m.group(1) + pre + "static/", html)
    def link(m):
        attr, url = m.group(1), m.group(2)
        base, _, frag = url.partition("#")
        if base in LOCAIS:
            return f'{attr}="{pre}{LOCAIS[base]}' + (f"#{frag}" if frag else "") + '"'
        if url == "/":
            return f'{attr}="{pre}"'
        return f'{attr}="{SITE_RENDER}{url}"'
    return re.sub(r'(href|action)="(/(?!/)[^"]*)"', link, html)


def _salvar(saida: Path, caminho: str, html: str):
    destino = saida / caminho / "index.html" if caminho else saida / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")


def gerar(saida: Path):
    saida.mkdir(parents=True, exist_ok=True)
    for velho in ("static", "studio", "termos", "politica", "novidades"):
        shutil.rmtree(saida / velho, ignore_errors=True)
    # arquivos estáticos (Studio + site)
    shutil.copytree(RAIZ / "Rolox-Studio/static", saida / "static")
    for f in (RAIZ / "Rolox-App/flask/static").iterdir():
        if f.is_file():
            shutil.copy2(f, saida / "static" / f.name)
    scripts = saida / "static/studio/scripts.js"          # import absoluto → relativo ao módulo
    scripts.write_text(scripts.read_text(encoding="utf-8").replace(
        'import("/static/vendor/pyodide/pyodide.mjs")', 'import("../vendor/pyodide/pyodide.mjs")'), encoding="utf-8")

    # Studio (o servidor local do Studio renderiza as páginas)
    sys.path.insert(0, str(RAIZ / "Rolox-Studio"))
    import servidor as studio_srv
    cli = studio_srv.criar_app().test_client()
    for modo in ("pc", "leve"):
        html = cli.get(f"/studio/{modo}").get_data(as_text=True)
        _salvar(saida, f"studio/{modo}", _relativo(html, "../../"))

    # páginas públicas do site
    sys.path.insert(0, str(RAIZ / "Rolox-App/flask"))
    import app as site
    from rolox_api import RoloxAPI
    cli = site.criar_app(lambda s: RoloxAPI(s, url="https://exemplo.invalid", chave="publica"), segredo="pages").test_client()
    for rota, pasta in LOCAIS.items():
        html = cli.get(rota).get_data(as_text=True)
        _salvar(saida, pasta.rstrip("/"), _relativo(html, "../"))

    _salvar(saida, "", INICIO.replace("{SITE}", SITE_RENDER))
    (saida / ".nojekyll").write_text("")                  # serve pastas que começam com _ sem Jekyll
    (saida / "404.html").write_text(INICIO.replace("{SITE}", SITE_RENDER), encoding="utf-8")


INICIO = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROLOX</title><link rel="icon" href="static/favicon.png"><link rel="stylesheet" href="static/rolox.css">
<style>.capa{max-width:560px;margin:40px auto;padding:0 16px;text-align:center}.capa img{max-width:320px;width:80%}
.capa .btn{display:block;margin:10px 0}.rodape-links{margin-top:24px}</style></head>
<body><main class="capa">
<img src="static/logo_nome.png" alt="ROLOX">
<p>Jogue, crie e divirta-se com os amigos. Grátis.</p>
<a class="btn" href="{SITE}/">▶ Jogar no ROLOX</a>
<a class="btn contorno" href="studio/pc/">🧱 Abrir o Studio (PC)</a>
<a class="btn contorno" href="studio/leve/">📱 Studio leve (celular)</a>
<p class="nota">O Studio roda direto no navegador. Para jogar online, fazer login e enviar mapas, use o botão Jogar.</p>
<p class="rodape-links"><a href="novidades/">📰 Novidades</a> · <a href="termos/">Termos de Uso</a> · <a href="politica/">Política de Uso</a>
 · <a href="https://discord.gg/6NZ5Ftq3p" target="_blank" rel="noopener">Discord</a></p>
</main></body></html>
"""

if __name__ == "__main__":
    gerar(Path(sys.argv[1] if len(sys.argv) > 1 else "pages"))
    print("ok")
