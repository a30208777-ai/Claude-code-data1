// Rolox Studio — modelos prontos para começar um jogo ("Novo").

import { Color3, Vector3, criar, mundoInicial } from "./motor.js";

function peca(pai, nome, pos, tam, cor, extra = {}) {
  const p = criar(extra.classe || "Part");
  p.Name = nome; p.Anchored = true;
  p.Size = Vector3.de(tam); p.Position = Vector3.de(pos); p.Color = Color3.fromHex(cor);
  for (const [k, v] of Object.entries(extra)) if (k !== "classe") p[k] = v;
  p.Parent = pai;
  return p;
}

function script(classe, pai, nome, lang, codigo) {
  const s = criar(classe);
  s.Name = nome;
  s.Source = `_++linguagemprogroma++_ = ${lang}\n${codigo.trim()}\n`;
  s.Parent = pai;
  return s;
}

function vazio() { return mundoInicial(); }

function obby() {
  const m = mundoInicial();
  const w = m.workspace;
  w.Chao.Color = Color3.fromHex("#37474f");
  const fase = criar("Folder"); fase.Name = "Plataformas"; fase.Parent = w;
  const lavas = criar("Folder"); lavas.Name = "Lavas"; lavas.Parent = w;
  // lava em todo o caminho; plataformas por cima
  peca(lavas, "LavaGrande", [0, 0.6, -60], [40, 0.4, 100], "#ff5722");
  const passos = [[0, 2, -14], [5, 4, -22], [-2, 6, -30], [-8, 8, -38], [-2, 9, -48], [6, 10, -57], [6, 12, -67], [0, 13, -77], [0, 14, -88]];
  passos.forEach(([x, y, z], i) => peca(fase, `Plataforma${i + 1}`, [x, y, z], [6, 1, 6], i % 2 ? "#29b6f6" : "#ab47bc"));
  peca(fase, "Barreira", [6, 13.5, -62], [8, 2, 1], "#ffca28", { CanCollide: true });
  peca(lavas, "LavaMovel", [0, 15, -82], [6, 1, 1], "#ff5722");
  const cp = peca(w, "Checkpoint", [-2, 9.6, -48], [6, 0.2, 6], "#66bb6a", { CanCollide: false });
  cp.Transparency = 0.3;
  peca(w, "Chegada", [0, 15, -98], [10, 1, 10], "#ffd600", { classe: "SpawnLocation" }).Name = "Chegada";

  script("LocalScript", m.game.StarterPlayer.StarterPlayerScripts, "Obby", "lua", `
-- Obby: lava mata, checkpoint salva, chegada mostra o tempo. (Luau: tipos, +=, \`texto {valor}\`)
local jogador = game.Players.LocalPlayer
local tempo: number = 0
local terminou = false
local checkpoint: Vector3? = nil

-- placar (leaderstats): aparece na tela e vira o recorde no site
local stats = Instance.new("Folder", jogador)
stats.Name = "leaderstats"
local vitorias = Instance.new("IntValue", stats)
vitorias.Name = "Vitórias"

local function eDoJogador(peca): boolean
  return peca.Parent == jogador.Character
end

for _, lava in ipairs(workspace.Lavas:GetChildren()) do
  lava.Touched:Connect(function(outro)
    if eDoJogador(outro) then
      jogador.Character.Humanoid.Health = 0
    end
  end)
end

workspace.Checkpoint.Touched:Connect(function(outro)
  if eDoJogador(outro) and checkpoint == nil then
    checkpoint = workspace.Checkpoint.Position + Vector3.new(0, 4, 0)
    print("✅ Checkpoint salvo!")
  end
end)

jogador.Character.Humanoid.Died:Connect(function()
  print("🔥 Caiu na lava! Tente de novo.")
  if checkpoint then
    task.delay(2.1, function()
      jogador.Character.HumanoidRootPart.Position = checkpoint
    end)
  end
end)

workspace.Chegada.Touched:Connect(function(outro)
  if eDoJogador(outro) and not terminou then
    terminou = true
    vitorias.Value += 1
    print(\`🏁 Você chegou em {math.floor(tempo * 10) / 10} segundos!\`)
  end
end)

game:GetService("RunService").Heartbeat:Connect(function(dt)
  if not terminou then tempo += dt end
end)

-- a lava móvel vai e volta
local lavaMovel = workspace.Lavas.LavaMovel
local x = 0
while true do
  x += 0.25
  lavaMovel.Position = Vector3.new(math.sin(x) * 4, 15, -82)
  wait(0.03)
end
`);
  return m;
}

function moedas() {
  const m = mundoInicial();
  const w = m.workspace;
  const pasta = criar("Folder"); pasta.Name = "Moedas"; pasta.Parent = w;
  const pontos = [[8, 2, -8], [-8, 2, -8], [12, 2, 6], [-12, 2, 6], [0, 2, -16], [16, 2, -16], [-16, 2, -16], [0, 6, -26], [6, 2, 14], [-6, 2, 14]];
  pontos.forEach((p, i) => peca(pasta, `Moeda${i + 1}`, p, [2, 0.5, 2], "#ffd600", { Shape: "Cylinder", CanCollide: false, Rotation: new Vector3(90, 0, 0) }));
  peca(w, "Rampa", [0, 2, -22], [8, 1, 8], "#8d6e63");
  peca(w, "Torre", [0, 4.5, -26], [6, 1, 6], "#8d6e63");
  script("Script", m.game.ServerScriptService, "Moedas", "python", `
# Coleta de moedas (Python): cada moeda vale 1 ponto e volta depois de 5 segundos.
# O placar fica em leaderstats (aparece na tela e vira recorde no site).
Players = game.GetService("Players")

def criar_placar(jogador):
    if jogador.FindFirstChild("leaderstats"):
        return
    stats = Instance.new("Folder", jogador)
    stats.Name = "leaderstats"
    moedas = Instance.new("IntValue", stats)
    moedas.Name = "Moedas"

for j in Players.GetChildren():
    criar_placar(j)
Players.PlayerAdded.Connect(criar_placar)

def conectar(moeda):
    async def pegou(outro):
        personagem = outro.Parent
        if moeda.Transparency > 0 or not personagem.FindFirstChildOfClass("Humanoid"):
            return
        jogador = Players.FindFirstChild(personagem.Name)   # outros jogadores da rede não contam aqui
        if not jogador or not jogador.FindFirstChild("leaderstats"):
            return
        jogador.leaderstats.Moedas.Value += 1
        print(f"🪙 {jogador.Name}: {jogador.leaderstats.Moedas.Value} moedas")
        moeda.Transparency = 1
        await wait(5)
        moeda.Transparency = 0
    moeda.Touched.Connect(pegou)

for moeda in workspace.Moedas.GetChildren():
    conectar(moeda)

# as moedas giram (Vector3 com operadores no Python)
def girar(dt):
    for moeda in workspace.Moedas.GetChildren():
        moeda.Rotation = moeda.Rotation + Vector3.new(0, 0, 180 * dt)

game.GetService("RunService").Heartbeat.Connect(girar)
print("Pegue as 10 moedas!")
`);
  return m;
}

export const MODELOS = [
  { id: "vazio", nome: "Vazio", descricao: "Chão e ponto de nascimento.", criar: vazio },
  { id: "obby", nome: "Obby (parkour)", descricao: "Plataformas sobre lava, checkpoint e cronômetro (Luau).", criar: obby },
  { id: "moedas", nome: "Coleta de moedas", descricao: "Moedas que giram e contam pontos (Python).", criar: moedas },
];
