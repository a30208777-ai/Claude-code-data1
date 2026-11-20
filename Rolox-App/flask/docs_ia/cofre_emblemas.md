palavras: salvar, salvo, progresso, guardar, carregar, cofre, datastore, nivel, level, xp, experiencia, emblema, emblemas, conquista, conquistas, badge, trofeu, premio, recompensa, inventario

# Receita: salvar progresso (Cofre) e conquistas (Emblemas)
Cofre = dados do PRÓPRIO jogador neste jogo, voltam na próxima vez que ele jogar. Use no LocalScript.
- `cofre:Ler(chave, padrao)` · `cofre:Salvar(chave, valor)` (número, texto ou true/false) · `cofre:Somar(chave, n)` devolve o novo valor
- `cofre:Apagar(chave)`. Chaves curtas sem espaço. Salva sozinho a cada 3 s e ao sair.
- Só funciona em jogo publicado e aprovado; no Studio funciona mas não fica salvo.

## Nível e XP
```lua
local cofre = game:GetService("Cofre")
local tela = game:GetService("Tela")
local xp, nivel = cofre:Ler("xp", 0), cofre:Ler("nivel", 1)
local function ganharXp(n)
  xp = xp + n
  if xp >= nivel * 100 then
    xp = xp - nivel * 100
    nivel = nivel + 1
    tela:Aviso("⬆️ Nível " .. nivel .. "!", 3)
    game:GetService("Sons"):Tocar("vitoria")
  end
  cofre:Salvar("xp", xp); cofre:Salvar("nivel", nivel)
  tela:Barra("xp", xp, nivel * 100, "topo")
  tela:Texto("nivel", "Nível " .. nivel, "topo")
end
ganharXp(0)
```
## Emblemas (aparecem no perfil do jogador no site)
`game:GetService("Emblemas"):Dar("codigo", "Nome bonito", "🏆")` — dá só uma vez (repetir não faz nada).
`Emblemas:Tem("codigo")` diz se já tem. Códigos curtos sem espaço. Ex.: primeira vitória, 100 moedas, achou o segredo.
