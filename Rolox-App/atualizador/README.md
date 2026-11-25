# Atualizador do VISTA

App Android oficial que **baixa, atualiza e abre o VISTA**. O VISTA só abre se o Atualizador
estiver instalado no aparelho (senão mostra o aviso de cópia pirata).

## O que ele faz
1. Lê `https://raw.githubusercontent.com/a30208777-ai/Rolox-apk/refs/heads/main/Vision-apk-link.json`:
   ```
   {
     "version": 0.20 ;
     "link": "https://...";
     "proctetion": "..."
   }
   ```
   (aceita `;` ou `,` no fim das linhas; a versão é lida como texto, então `0.20` é maior que `0.9`).
2. Compara a `version` com a última que ele baixou e avisa quando tem versão nova.
3. Baixa pelo `link`:
   - se o link entrega o `.apk` (ou um `.zip` com o `.apk` do VISTA dentro), extrai e abre o instalador do Android;
   - se o link é uma página de download (ex.: TransferNow), abre a página no navegador e o jogador baixa e instala por lá.
4. Na 1ª vez que abre, pergunta se quer **criar um atalho "VISTA" na tela inicial**; o atalho abre o VISTA.

## Para publicar uma versão nova do VISTA
Edite o `Vision-apk-link.json` no repositório **Rolox-apk** (branch `main`): aumente a `version` e troque o `link`.
Quem abrir o Atualizador vê "Tem versão nova do VISTA". Um link direto para o `.apk` instala sozinho;
um link de site de transferência abre no navegador.

## Como os dois apps se reconhecem
- VISTA abre por `rolox://abrir`; o Atualizador por `roloxatualizador://`.
- O VISTA pergunta ao Android se alguém abre `roloxatualizador://` (por isso declara `<queries>` no pyproject).
- Só vale no Android; no PC o VISTA abre normalmente.

## Rodar / testar
    flet run src/main.py      # no PC (instalar e atalho só funcionam no Android)
    python -m pytest -q
