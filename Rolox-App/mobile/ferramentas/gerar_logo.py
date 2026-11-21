"""Gera a logo do ROLOX (ícone do app, splash, logo da tela de login e favicon do site).

    python ferramentas/gerar_logo.py

Desenho próprio do ROLOX: um "R" em bloco 3D (o ROLOX é feito de peças), saindo de um bloco
inclinado, com a faísca laranja da criação. Tudo desenhado aqui (só precisa do Pillow e da
fonte Inter, que é livre). Desenha 4x maior e reduz no fim, para as bordas ficarem lisas.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = RAIZ / "src" / "assets"
SITE = RAIZ.parent / "flask" / "static"
ATUALIZADOR = RAIZ.parent / "atualizador" / "src" / "assets"     # o Atualizador usa a mesma logo
HACKS = RAIZ.parent / "hacks" / "src" / "assets"                 # ROLOX Hacks: a logo com o robô
FONTE = next((p for p in ("/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
                          "/usr/share/fonts/opentype/inter/Inter-Black.otf") if Path(p).exists()), None)
ESCALA = 4

ROXO_ESCURO = (38, 12, 92)
ROXO = (98, 50, 230)
CIANO = (0, 200, 255)
LARANJA = (255, 145, 0)
AMARELO = (255, 213, 79)


def degrade(n: int, c1, c2, c3) -> Image.Image:
    """Degradê diagonal de 3 cores (canto de cima à esquerda -> embaixo à direita)."""
    vert = Image.linear_gradient("L").resize((n, n))
    g = Image.blend(vert, vert.transpose(Image.TRANSPOSE), 0.5)   # (x + y) / 2: 0 em cima à esquerda
    meio = Image.new("RGB", (n, n), c2)
    a = Image.composite(meio, Image.new("RGB", (n, n), c1), g.point(lambda v: min(255, v * 2)))
    return Image.composite(Image.new("RGB", (n, n), c3), a, g.point(lambda v: max(0, v * 2 - 255)))


def mascara_letra(n: int, letra: str = "R") -> Image.Image:
    m = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(m)
    f = ImageFont.truetype(FONTE, int(n * 0.62)) if FONTE else ImageFont.load_default()
    x0, y0, x1, y1 = d.textbbox((0, 0), letra, font=f)
    d.text(((n - (x1 - x0)) / 2 - x0 - n * 0.02, (n - (y1 - y0)) / 2 - y0 - n * 0.03), letra, font=f, fill=255)
    return m


def faisca(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, cor) -> None:
    """Estrela de 4 pontas (a faísca da criação)."""
    pts = []
    for k in range(8):
        ang = math.pi / 4 * k - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=cor)


def marca(n: int) -> Image.Image:
    """Só o símbolo (fundo transparente): bloco inclinado + R 3D + faísca."""
    N = n * ESCALA
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))

    # bloco de fundo inclinado (um "tijolo" do ROLOX), com sombra
    bloco = Image.new("L", (N, N), 0)
    ImageDraw.Draw(bloco).rounded_rectangle((N * 0.17, N * 0.17, N * 0.83, N * 0.83), radius=N * 0.13, fill=255)
    bloco = bloco.rotate(-12, resample=Image.BICUBIC)
    sombra = bloco.filter(ImageFilter.GaussianBlur(N * 0.03))
    img.paste((10, 0, 40, 110), (0, int(N * 0.035)), sombra)
    cor_bloco = degrade(N, (124, 77, 255), (83, 109, 254), CIANO).convert("RGBA")
    img.paste(cor_bloco, (0, 0), bloco)
    # brilho na parte de cima do bloco
    brilho = Image.new("L", (N, N), 0)
    ImageDraw.Draw(brilho).ellipse((N * 0.05, -N * 0.35, N * 0.95, N * 0.48), fill=70)
    img.paste((255, 255, 255), (0, 0), ImageChops.multiply(brilho.filter(ImageFilter.GaussianBlur(N * 0.04)), bloco))

    # R em 3D: camadas empilhadas para dar profundidade (para baixo e à direita)
    letra = mascara_letra(N)
    prof = int(N * 0.055)
    for k in range(prof, 0, -1):
        t = k / prof
        cor = (int(30 + 40 * (1 - t)), int(8 + 10 * (1 - t)), int(80 + 60 * (1 - t)))
        img.paste(cor, (k, k), letra)
    # frente do R: branco com leve degradê para cima
    frente = Image.linear_gradient("L").resize((N, N)).point(lambda v: 255 - v // 6)
    branco = Image.merge("RGB", (frente, frente, frente.point(lambda v: min(255, v + 8))))
    img.paste(branco, (0, 0), letra)
    # contorno fino na frente (separa da extrusão)
    borda = letra.filter(ImageFilter.MaxFilter(5)).point(lambda v: 255 if v else 0)
    borda = ImageChops.subtract(borda, letra)
    img.paste((235, 230, 255), (0, 0), borda)

    # faísca laranja no canto (com um brilhinho)
    d = ImageDraw.Draw(img)
    cx, cy, r = N * 0.79, N * 0.21, N * 0.11
    glow = Image.new("L", (N, N), 0)
    ImageDraw.Draw(glow).ellipse((cx - r * 1.2, cy - r * 1.2, cx + r * 1.2, cy + r * 1.2), fill=120)
    img.paste(AMARELO, (0, 0), glow.filter(ImageFilter.GaussianBlur(N * 0.03)))
    faisca(d, cx, cy, r, LARANJA)
    faisca(d, cx, cy, r * 0.55, AMARELO)
    faisca(d, N * 0.88, N * 0.34, r * 0.32, (255, 255, 255))
    return img.resize((n, n), Image.LANCZOS)


def robo(n: int) -> Image.Image:
    """Selo do ROLOX Hacks: carinha de robô num círculo laranja (desenhada, sem emoji)."""
    N = n * ESCALA
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, N - 1, N - 1), fill=(255, 109, 0), outline=(255, 255, 255), width=int(N * 0.06))
    cab = (N * 0.24, N * 0.33, N * 0.76, N * 0.74)
    d.rounded_rectangle(cab, radius=N * 0.1, fill=(255, 255, 255))
    d.line((N * 0.5, N * 0.33, N * 0.5, N * 0.2), fill=(255, 255, 255), width=int(N * 0.05))
    d.ellipse((N * 0.44, N * 0.13, N * 0.56, N * 0.25), fill=(255, 255, 255))
    for x in (0.38, 0.62):
        d.ellipse((N * (x - 0.07), N * 0.45, N * (x + 0.07), N * 0.59), fill=(38, 12, 92))
    d.rounded_rectangle((N * 0.38, N * 0.63, N * 0.62, N * 0.68), radius=N * 0.02, fill=(38, 12, 92))
    return img.resize((n, n), Image.LANCZOS)


def icone(n: int = 1024, hacks: bool = False) -> Image.Image:
    """Ícone do app: fundo em degradê (sangra até a borda) + símbolo. `hacks`: versão do ROLOX Hacks."""
    N = n * ESCALA
    cores = ((20, 8, 30), (70, 20, 60), (191, 54, 12)) if hacks else (ROXO_ESCURO, (74, 20, 140), (13, 71, 161))
    fundo = degrade(N, *cores).convert("RGBA")
    # luz suave atrás do símbolo
    luz = Image.new("L", (N, N), 0)
    ImageDraw.Draw(luz).ellipse((N * 0.12, N * 0.1, N * 0.88, N * 0.86), fill=110)
    fundo.paste((255, 109, 0) if hacks else (124, 77, 255), (0, 0), luz.filter(ImageFilter.GaussianBlur(N * 0.12)))
    fundo = fundo.resize((n, n), Image.LANCZOS)
    m = marca(int(n * 0.84))                      # margem para o recorte redondo do Android
    fundo.alpha_composite(m, ((n - m.width) // 2, (n - m.height) // 2))
    if hacks:
        r = robo(int(n * 0.3))
        fundo.alpha_composite(r, (int(n * 0.6), int(n * 0.6)))
    return fundo.convert("RGB")


def icone_android(n: int = 1024, hacks: bool = False, escala: float = 0.6) -> Image.Image:
    """Camada da frente do ícone ADAPTATIVO do Android (fundo transparente; a cor vem do
    adaptive_icon_background). O Android só mostra os 66% do meio desta imagem, então o desenho
    fica pequeno no centro; senão a logo aparece ampliada e cortada na tela inicial."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    m = marca(int(n * escala))
    if hacks:
        r = robo(int(m.width * 0.42))
        m.alpha_composite(r, (m.width - r.width, m.height - r.height))
    img.alpha_composite(m, ((n - m.width) // 2, (n - m.height) // 2))
    return img


def logo_com_nome(altura: int = 220, nome: str = "ROLOX", hacks: bool = False) -> Image.Image:
    """Símbolo + 'ROLOX' (para telas e para o site). `hacks`: 'ROLOX HACKS' em laranja."""
    m = marca(altura)
    if hacks:
        r = robo(int(altura * 0.42))
        m.alpha_composite(r, (altura - r.width, altura - r.height))
    f = ImageFont.truetype(FONTE, int(altura * 0.5)) if FONTE else ImageFont.load_default()
    medir = ImageDraw.Draw(Image.new("L", (1, 1)))
    x0, y0, x1, y1 = medir.textbbox((0, 0), nome, font=f)
    larg = altura + int(altura * 0.12) + (x1 - x0) + 8
    img = Image.new("RGBA", (larg, altura), (0, 0, 0, 0))
    img.alpha_composite(m, (0, 0))
    texto = Image.new("L", img.size, 0)
    ImageDraw.Draw(texto).text((altura + int(altura * 0.12) - x0, (altura - (y1 - y0)) / 2 - y0), nome, font=f, fill=255)
    cores = ((255, 171, 64), (255, 109, 0), (221, 44, 0)) if hacks else ((124, 77, 255), (98, 50, 230), (0, 176, 255))
    cor = degrade(max(img.size), *cores).crop((0, 0, *img.size))
    img.paste(cor, (0, 0), texto)
    return img


def main() -> None:
    if not FONTE:
        sys.exit("Instale a fonte Inter (fonts-inter) para gerar a logo.")
    ASSETS.mkdir(parents=True, exist_ok=True)
    icone(1024).save(ASSETS / "icon.png", optimize=True)
    marca(1024).save(ASSETS / "splash.png", optimize=True)
    marca(512).save(ASSETS / "logo.png", optimize=True)
    logo_com_nome(220).save(ASSETS / "logo_nome.png", optimize=True)
    icone_android().save(ASSETS / "icon_android.png", optimize=True)
    if ATUALIZADOR.parent.is_dir():
        ATUALIZADOR.mkdir(exist_ok=True)
        icone(1024).save(ATUALIZADOR / "icon.png", optimize=True)
        icone_android().save(ATUALIZADOR / "icon_android.png", optimize=True)
        marca(1024).save(ATUALIZADOR / "splash.png", optimize=True)
        logo_com_nome(220).save(ATUALIZADOR / "logo_nome.png", optimize=True)
    if HACKS.parent.is_dir():
        HACKS.mkdir(exist_ok=True)
        icone(1024, hacks=True).save(HACKS / "icon.png", optimize=True)
        icone_android(hacks=True).save(HACKS / "icon_android.png", optimize=True)
        logo_com_nome(220, "ROLOX HACKS", hacks=True).save(HACKS / "logo_nome.png", optimize=True)
        im = marca(1024); r = robo(330); im.alpha_composite(r, (1024 - 330 - 60, 1024 - 330 - 60))
        im.save(HACKS / "splash.png", optimize=True)
    if SITE.is_dir():
        logo_com_nome(120).save(SITE / "logo_nome.png", optimize=True)
        marca(256).save(SITE / "logo.png", optimize=True)
        icone(180).save(SITE / "apple-touch-icon.png", optimize=True)
        icone(64).save(SITE / "favicon.png", optimize=True)
    print("logo gerada em", ASSETS, "e", SITE)


if __name__ == "__main__":
    main()
