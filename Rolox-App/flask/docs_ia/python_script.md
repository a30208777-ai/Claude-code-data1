palavras: python, servidor, serverscriptservice, async, await, def, py, script do servidor

# Python no VISTA (Script em ServerScriptService)
Diferenças para Lua:
- Métodos e eventos com PONTO: `peca.Touched.Connect(funcao)`, `game.GetService("Rede")`, `peca.FindFirstChildOfClass("Humanoid")`.
- Esperar: a função precisa ser `async def` e usar `await wait(2)`. Funções ligadas em Connect podem ser async.
- Laços infinitos: `while True:` com `await wait(1)` dentro, dentro de um `async def`, iniciado com `task.spawn(funcao)`.
- Booleanos True/False, nulo None, texto com f"...". Variável global alterada dentro de função precisa de `global nome`.
- Disponível: game, workspace, Instance.new(classe, pai), Vector3.new(x,y,z) (soma com +), Color3.fromRGB(r,g,b), task, wait, print.

## Exemplo: rodadas com contagem para todos
```python
rede = game.GetService("Rede")

async def rodadas():
    while True:
        for s in range(10, 0, -1):
            rede.ParaTodos("contagem", s)
            await wait(1)
        rede.ParaTodos("contagem", "VALENDO!")
        workspace.Portao.CanCollide = False
        workspace.Portao.Transparency = 0.8
        await wait(30)
        workspace.Portao.CanCollide = True
        workspace.Portao.Transparency = 0

task.spawn(rodadas)
```
E no LocalScript: `rede.RecebidoDoServidor:Connect(function(nome, d) if nome == "contagem" then tela:Texto("tempo", "⏱️ " .. tostring(d), "topo") end end)`.

## Toque em Python
```python
pronto = True
async def tocou(outro):
    global pronto
    h = outro.Parent and outro.Parent.FindFirstChildOfClass("Humanoid")
    if not h or not pronto:
        return
    pronto = False
    h.Health = h.Health - 20
    await wait(1)
    pronto = True
workspace.Espinho.Touched.Connect(tocou)
```
