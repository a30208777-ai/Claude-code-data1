"""Baixa o Pyodide (Python no navegador, ~14 MB) para static/vendor/pyodide.

Opcional: sem ele, o Studio baixa o Pyodide da internet (jsdelivr) na hora
em que um script Python roda. Com ele, funciona sem internet.

    python baixar_pyodide.py
"""

import io
import shutil
import tarfile
import urllib.request
from pathlib import Path

VERSAO = "314.0.8"
URL = f"https://registry.npmjs.org/pyodide/-/pyodide-{VERSAO}.tgz"
DESTINO = Path(__file__).resolve().parent / "static" / "vendor" / "pyodide"


def main() -> None:
    print(f"Baixando Pyodide {VERSAO}...")
    with urllib.request.urlopen(URL, timeout=120) as r:
        dados = r.read()
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as tar:
        for membro in tar.getmembers():
            if not membro.isfile() or not membro.name.startswith("package/"):
                continue
            nome = Path(membro.name).relative_to("package")
            if ".." in nome.parts:
                continue
            alvo = DESTINO / nome
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(membro) as origem, open(alvo, "wb") as saida:
                shutil.copyfileobj(origem, saida)
    print(f"Pronto: {DESTINO}")


if __name__ == "__main__":
    main()
