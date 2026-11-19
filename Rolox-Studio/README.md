# Rolox Studio — primeira versão

Editor de jogos do Rolox, que roda no navegador e tem duas versões:

| | 📱 **Studio leve** (`/studio/leve`) | 🖥️ **Studio PC** (`/studio/pc`) |
|---|---|---|
| Para | celular | computador |
| Gráficos | sem sombras, sem antialiasing, resolução 1× | sombras, antialiasing, resolução alta |
| Interface | uma área por vez + abas embaixo, botões grandes | Explorer, cena, Propriedades e Saída lado a lado |
| Mover/escalar | pelas Propriedades | setas na cena (Mover `W` / Escalar `R`) + Propriedades |
| Peças | até 400 | até 5000 |
| PCtoCelular | escondido (você já está no celular) | painel completo |
| Python | carrega só quando um script Python roda | já começa a carregar ao abrir |

## Rodar

```bash
cd Rolox-Studio
pip install -r requirements.txt
python servidor.py            # abra http://localhost:8600
```

No **Termux** é igual (`pkg install python` antes). O Flask e o flask-sock são Python puro, então não precisam compilar nada.
Opcional, para usar o Python dos scripts sem internet: `python baixar_pyodide.py` (~14 MB).

## O que dá para fazer
- **Peças:** Bloco, Bola, Cilindro, SpawnLocation, Pasta e Model, com Position, Size, Rotation, Color, Anchored, CanCollide, Transparency e Shape.
- **Explorer:** Workspace, ServerScriptService, ReplicatedStorage e StarterPlayer > StarterPlayerScripts; trocar o Parent; duplicar (Ctrl+D) e apagar (Delete).
- **Jogar (F5):** testa o jogo no próprio Studio, com personagem em blocos, gravidade, colisão, pulo, `Humanoid` (WalkSpeed, JumpPower, Health, Died) e `Touched`. Ao parar, tudo volta como estava antes do teste.
- **Controles:** WASD/setas e espaço no PC; joystick e botão de pulo na tela de toque.
- **Salvar/Abrir:** os projetos ficam na pasta `projetos/`, e dá para exportar e importar um arquivo `.rolox`. Também há um rascunho automático no navegador.

## Scripts: Lua (Luau) e Python

| Tipo | Onde roda | Linguagem padrão |
|---|---|---|
| **LocalScript** | no dispositivo do jogador ("local") | **Lua** |
| **Script** | no servidor ("server script") | **Python** |
| **ModuleScript** | onde for chamado com `require()` | **Lua ou Python**, quem decide é o dono do jogo |

A linguagem fica na **primeira linha** do script, e isso vale para os três tipos:

```
_++linguagemprogroma++_ = lua
_++linguagemprogroma++_ = python
```

Trocar a linguagem de um **LocalScript para Python** mostra o aviso:

> Ei!!! Se você mudar para Python, o seu jogo pode perder jogadores (retenção), porque o usuário precisa rodar Python no celular dele pelo Termux. Para saber mais, **clique aqui**.

O "clique aqui" abre `/aprender/python-no-celular`, que por enquanto é uma página "em construção".

### Exemplo em Lua (LocalScript)
```lua
_++linguagemprogroma++_ = lua
local p = Instance.new("Part", workspace)
p.Anchored = true
p.Position = Vector3.new(0, 3, -10) + Vector3.new(1, 0, 0)
p.Color = Color3.fromRGB(255, 0, 0)
p.Touched:Connect(function(outro)
  local hum = outro.Parent:FindFirstChildOfClass("Humanoid")
  if hum then hum.Health = 0 end
end)
wait(1)
print("Olá,", game.Players.LocalPlayer.Name)
```

### Exemplo em Python (Script do servidor)
```python
_++linguagemprogroma++_ = python
moeda = workspace.Moeda
async def pegou(outro):
    if outro.Parent.FindFirstChildOfClass("Humanoid"):
        moeda.Transparency = 1
        await wait(5)
        moeda.Transparency = 0
moeda.Touched.Connect(pegou)
```

### O que a API já tem
`game`, `workspace`, `script`, `game:GetService(...)`, `Instance.new`, `Vector3.new` (com `+ - * /` no Lua), `Color3.new/fromRGB`, `wait`, `task.wait/spawn/delay`, `print`, `warn`, `require`, `:Connect`, `:Wait`, `:Disconnect`, `FindFirstChild`, `FindFirstChildOfClass`, `GetChildren`, `GetDescendants`, `IsA`, `Clone`, `Destroy`, acesso a filhos pelo nome (`workspace.Chao`), `Players.LocalPlayer`, `Character`, `Humanoid`, `RunService.Heartbeat` e `Touched/TouchEnded`.

**Regras do `require`:** script Lua usa módulo Lua, e script Python usa módulo Python. Misturar as duas linguagens ainda não é possível.

## Importar `.obj` (por exemplo, do Roblox Studio)
1. No Roblox Studio, selecione o modelo, clique com o botão direito, escolha **Export Selection…** e salve. Ele gera `.obj`, `.mtl` e as texturas `.png`.
2. No Rolox Studio, clique em **Importar .obj** e escolha **todos os arquivos juntos**: o `.obj`, o `.mtl` e as texturas.
3. A malha vira um **MeshPart** com o tamanho real do modelo e fica salva dentro do projeto.

Importe só modelos que **você criou** ou que tem permissão para usar.

## PCtoCelular
O celular vira controle do jogo no PC: **inclinar** o celular faz o personagem andar, e **levantar rápido** faz pular. O Studio também mede a inclinação, o giro e uma altura estimada.

- **Limites:** até **5 celulares por Bluetooth** e **2 por cabo**. Cada celular vira um jogador.
- **Privacidade:** os dados do sensor **não vão para nenhum lugar**. Eles vão só do celular para o servidor do Studio no próprio PC, ficam na memória e não são gravados.
- **Sem sensor:** se o celular não tiver sensor de movimento, ou se o navegador bloquear, a página vira o **controle padrão**, com joystick e botão de pular.
- **Jogando pelo celular:** quem usa o Studio leve não vê essa mecânica.

**Por cabo (USB):**
1. Ligue a depuração USB no celular e conecte o cabo.
2. No PC, rode `adb reverse tcp:8600 tcp:8600`.
3. No celular, abra `http://localhost:8600/controle` e digite o código de 4 dígitos que aparece no painel do PC.

Pelo cabo, o endereço é `localhost`, que o navegador considera seguro, então o sensor de movimento funciona.

**Por Bluetooth:**
1. No celular, ligue a **ancoragem Bluetooth** e pareie com o PC.
2. No PC, rode `ROLOX_HOST=0.0.0.0 python servidor.py`.
3. No celular, abra `http://IP-DO-PC:8600/controle`. O IP aparece no painel.

Pelo Bluetooth a página abre por `http` comum, e a maioria dos navegadores só libera o sensor em conexão segura. Por isso, nesse caminho ele costuma cair no joystick.

**Segurança:** mesmo com `ROLOX_HOST=0.0.0.0`, o Studio e os projetos só abrem no próprio PC. Outros aparelhos só acessam a página `/controle`, e só conectam com o código.

## Testes
```bash
pip install pytest && python -m pytest -q     # servidor (14)
node --test tests/*.test.mjs                  # motor e física (7)
```
Também testei no navegador, como PC e como celular simulado:
- **Scripts:** Lua e Python, `require`, `Touched`, `Died` e `wait`, inclusive dentro de evento em Python.
- **Física:** pulo, caminhada e física.
- **Arquivos:** importar `.obj` e salvar/abrir projetos.
- **PCtoCelular:** código errado e código certo; o celular move um segundo jogador.
- **Studio leve:** abas e joystick.

## Limites desta primeira versão
- **Luau:** o Lua roda no Fengari (Lua 5.3). Os tipos do Luau (`local x: number`) ainda não funcionam. Já existem `math.clamp`, `math.round`, `string.split` e `table.find`.
- **Vector3 no Python:** use `v.add(outro)`, `v.sub(outro)` e `v.mul(n)`, porque o `+` ainda não funciona com Vector3 em Python.
- **Física:** usa caixas alinhadas aos eixos. A Rotation aparece no desenho, mas ainda não entra na colisão.
- **Servidor e local:** no teste dentro do Studio, os scripts de servidor e os locais rodam no mesmo aparelho. O servidor de jogo de verdade, com multiplayer, é a Fase 13 da arquitetura.
- **Arquivos do Roblox:** só `.obj` é importado. `.rbxl` e `.rbxm` não são.
- **Python:** roda no navegador pelo Pyodide. A primeira vez baixa cerca de 10 MB.

Bibliotecas incluídas: Three.js r187 e Fengari, ambas com licença MIT (arquivos LICENSE em `static/vendor`). O Pyodide (MPL-2.0) é carregado da internet ou baixado com `baixar_pyodide.py`.
