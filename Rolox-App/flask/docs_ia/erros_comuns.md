palavras: erro, erros, bug, bugs, nao funciona, nao funcionou, quebrou, travou, trava, nil, attempt to index, consertar, corrigir, arrumar, problema, ajuda, por que

# Erros comuns e como consertar
- "attempt to index nil" → a peça não existe com esse nome ou está em outra pasta. Confira no MAPA ATUAL o nome
  exato (maiúsculas contam) e o caminho (workspace.Casa.Porta). Use FindFirstChild e teste `if not p then return end`.
- Evento dispara várias vezes → falta "debounce" (variável pronto/aberta).
- O chão ou outra peça ativa o Touched → falta conferir o Humanoid.
- Jogo travou → laço `while true do` sem `wait(...)` dentro.
- Script não roda → LocalScript fora de StarterPlayerScripts, ou Script fora de ServerScriptService.
  Linguagem errada: Lua usa `:`/`end`, Python usa `.`/indentação. Linha `_++linguagemprogroma++_ = lua` troca.
- Peça caiu e sumiu → estava com Anchored = false. Peça atravessa → CanCollide = false.
- Em Python "await fora de async" → coloque o código dentro de `async def` e rode com `task.spawn(funcao)`.
- Python "nome não definido" ao mudar variável → falta `global nome` dentro da função.
- Mudança só aparece para um jogador → foi feita em LocalScript; para todos verem use Script (Python).
Ao consertar: use {"acao":"editar","alvo":"StarterPlayerScripts.NomeDoScript","codigo":"...código inteiro corrigido..."}
e explique em uma frase qual era o erro.
