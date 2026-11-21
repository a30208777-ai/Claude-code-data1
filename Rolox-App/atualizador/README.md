# Atualizador do ROLOX

App Android oficial que **baixa, atualiza e abre o ROLOX**. O ROLOX só abre se o Atualizador
estiver instalado no aparelho (senão mostra o aviso de cópia pirata).

## O que ele faz
1. Baixa o ROLOX de `https://github.com/a30208777-ai/Rolox-apk/archive/refs/heads/main.zip`.
2. Extrai do `.zip` só o `.apk` do ROLOX (o arquivo com "rolox" no nome; se tiver vários, o de versão maior).
3. Abre o instalador do Android (a 1ª vez o Android pede para permitir "instalar apps desconhecidos").
4. Na 1ª vez que abre, pergunta se quer **criar um atalho "ROLOX" na tela inicial**; o atalho abre o ROLOX.
5. Avisa quando tem versão nova (compara com o último commit do repositório `Rolox-apk`).

## Para publicar uma versão nova do ROLOX
Coloque o `.apk` do ROLOX (do Actions → artefato `rolox-apk`) no repositório **Rolox-apk**, branch `main`.
Na próxima vez que alguém abrir o Atualizador, ele avisa que tem versão nova.

## Como os dois apps se reconhecem
- ROLOX abre por `rolox://abrir`; o Atualizador por `roloxatualizador://`.
- O ROLOX pergunta ao Android se alguém abre `roloxatualizador://` (por isso declara `<queries>` no pyproject).
- Só vale no Android; no PC o ROLOX abre normalmente.

## Rodar / testar
    flet run src/main.py      # no PC (instalar e atalho só funcionam no Android)
    python -m pytest -q
