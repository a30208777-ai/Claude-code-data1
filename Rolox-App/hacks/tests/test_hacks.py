import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_configuracao():
    cfg = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    assert cfg["tool"]["flet"]["bundle_id"] == "com.rolox.hacks"
    assert cfg["tool"]["flet"]["product"] == "ROLOX Hacks"
    assert any(d.startswith("flet-webview") for d in cfg["project"]["dependencies"])
    for f in ("icon.png", "splash.png", "logo_nome.png"):
        assert (RAIZ / "src" / "assets" / f).exists(), f


def test_abre_a_area_de_hacks_do_site():
    import main
    assert main.URL_HACKS.endswith("/hacks") and main.URL_HACKS.startswith("https://")
