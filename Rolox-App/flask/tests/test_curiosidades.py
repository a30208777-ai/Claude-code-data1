import importlib.util
from pathlib import Path

import curiosidades


def test_lista_do_site_e_do_app_sao_iguais():
    caminho = Path(__file__).resolve().parents[2] / "mobile" / "src" / "rolox" / "curiosidades.py"
    spec = importlib.util.spec_from_file_location("curiosidades_app", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CURIOSIDADES == curiosidades.CURIOSIDADES


def test_curiosidades_pedidas_e_sem_repetir():
    lista = curiosidades.CURIOSIDADES
    assert "O VISTA foi inspirado no ROBLOX." in lista
    assert any("decisões ruins do ROBLOX" in c for c in lista)
    assert len(lista) == len(set(lista)) >= 15
    assert all(c.strip() and len(c) <= 140 for c in lista)
    assert sorted(curiosidades.embaralhadas(1)) == sorted(lista)
