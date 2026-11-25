palavras: internet, pesquisar, pesquisa, buscar na internet, wikipedia, google, quiz, perguntas, pergunta, curiosidade, informacao, enciclopedia

# Receita: Internet (pesquisa segura feita pelo servidor do VISTA)
```lua
local net = game:GetService("Internet")
local tela = game:GetService("Tela")
net.Resultado:Connect(function(termo, texto)
  tela:Texto("info", texto, "centro")      -- texto = "Título: resumo" (até 3 resultados)
  task.delay(8, function() tela:Remover("info") end)
end)
net:Pesquisar("dinossauros")
```
- Só devolve TEXTO (Wikipédia e DuckDuckGo com busca segura). Não abre site, não baixa imagem.
- Até 20 pesquisas por minuto; pesquise quando o jogador pedir (botão), não em loop.
- Termos impróprios são recusados. Só funciona com o jogo aberto pelo site.
Ideia: totem com botão "📚 Curiosidade" que pesquisa um tema sorteado de uma lista
(`local temas = {"Saturno", "Tubarão", "Vulcão"}; net:Pesquisar(temas[math.random(#temas)])`).
