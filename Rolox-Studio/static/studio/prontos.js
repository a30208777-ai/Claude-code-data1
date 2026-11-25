// VISTA Studio — 📦 peças prontas: um toque e o objeto aparece na sua frente (já com script quando precisa).

import { Color3, Vector3, criar } from "./motor.js";

function peca(pai, nome, pos, tam, cor, material = "Plastico", extra = {}) {
  const p = criar(extra.classe || "Part");
  p.Name = nome; p.Anchored = true;
  p.Size = new Vector3(...tam); p.Position = new Vector3(...pos);
  p.Color = Color3.fromHex(cor); p.Material = material;
  if (extra.forma) p.Shape = extra.forma;
  if (extra.colide === false) p.CanCollide = false;
  if (extra.transparencia) p.Transparency = extra.transparencia;
  p.Parent = pai;
  return p;
}
function script(pai, nome, codigo) {
  const s = criar("Script");
  s.Name = nome;
  s.Source = "_++linguagemprogroma++_ = lua\n" + codigo;   // Script em Lua: roda no anfitrião (todos veem)
  s.Parent = pai;
  return s;
}

export const PRONTOS = {
  arvore: { nome: "🌳 Árvore", fazer(m, b) {
    peca(m, "Tronco", [b.X, b.Y + 3, b.Z], [1.5, 6, 1.5], "#6d4c41", "Madeira", { forma: "Cylinder" });
    peca(m, "Copa", [b.X, b.Y + 7.5, b.Z], [6, 6, 6], "#2e7d32", "Grama", { forma: "Ball" });
  } },
  casa: { nome: "🏠 Casa", fazer(m, b) {
    const P = (n, dx, dy, dz, sx, sy, sz, cor = "#efebe9", mat = "Tijolo") => peca(m, n, [b.X + dx, b.Y + dy, b.Z + dz], [sx, sy, sz], cor, mat);
    P("Piso", 0, 0.25, 0, 12, 0.5, 12, "#8d6e63", "Madeira");
    P("Fundo", 0, 4.5, -5.5, 12, 8, 1); P("Esquerda", -5.5, 4.5, 0, 1, 8, 12); P("Direita", 5.5, 4.5, 0, 1, 8, 12);
    P("FrenteE", -3.75, 4.5, 5.5, 4.5, 8, 1); P("FrenteD", 3.75, 4.5, 5.5, 4.5, 8, 1); P("SobrePorta", 0, 7, 5.5, 3, 3, 1);
    P("Teto", 0, 9, 0, 13, 1, 13, "#c62828", "Madeira");
  } },
  ponte: { nome: "🌉 Ponte", fazer(m, b) {
    peca(m, "Tabuas", [b.X, b.Y + 0.25, b.Z], [5, 0.5, 24], "#8d6e63", "Madeira");
    peca(m, "CorrimaoE", [b.X - 2.4, b.Y + 1.5, b.Z], [0.3, 2, 24], "#5d4037", "Madeira");
    peca(m, "CorrimaoD", [b.X + 2.4, b.Y + 1.5, b.Z], [0.3, 2, 24], "#5d4037", "Madeira");
  } },
  escada: { nome: "🪜 Escada", fazer(m, b) {
    for (let i = 0; i < 8; i++) peca(m, `Degrau${i + 1}`, [b.X, b.Y + 0.5 + i, b.Z - i * 1.5], [4, 1, 1.5], "#9e9e9e", "Concreto");
  } },
  trampolim: { nome: "🦘 Trampolim", fazer(m, b) {
    peca(m, "Trampolim", [b.X, b.Y + 0.5, b.Z], [6, 1, 6], "#e91e63", "Borracha");
  } },
  lava: { nome: "🌋 Lava que machuca", fazer(m, b) {
    peca(m, "Lava", [b.X, b.Y + 0.25, b.Z], [10, 0.5, 10], "#ff5722", "Lava");
    script(m, "DanoLava", `local lava = script.Parent:FindFirstChild("Lava")
lava.Touched:Connect(function(outro)
  local h = outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")
  if h and h.Health > 0 then h.Health = 0 end
end)`);
  } },
  porta: { nome: "🚪 Porta automática", fazer(m, b) {
    peca(m, "Porta", [b.X, b.Y + 4, b.Z], [6, 8, 1], "#8d6e63", "Madeira");
    peca(m, "Sensor", [b.X, b.Y + 4, b.Z + 3], [6, 8, 5], "#00e5ff", "Vidro", { colide: false, transparencia: 0.9 });
    script(m, "AbrirPorta", `local porta = script.Parent:FindFirstChild("Porta")
local sensor = script.Parent:FindFirstChild("Sensor")
local anim = game:GetService("Animar")
local fechada = porta.Position
local aberta = false
sensor.Touched:Connect(function(outro)
  if aberta or not (outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")) then return end
  aberta = true
  anim:Mover(porta, fechada + Vector3.new(0, 7.5, 0), 0.6)
  game:GetService("Sons"):Tocar("porta")
  wait(3)
  anim:Mover(porta, fechada, 0.6)
  wait(0.7)
  aberta = false
end)`);
  } },
  moeda: { nome: "🪙 Moeda (com placar)", fazer(m, b) {
    peca(m, "Moeda", [b.X, b.Y + 2, b.Z], [2, 2, 0.4], "#ffc400", "Metal", { forma: "Cylinder", colide: false });
    script(m, "PegarMoeda", `local moeda = script.Parent:FindFirstChild("Moeda")
local anim = game:GetService("Animar")
anim:Girar(moeda, Vector3.new(0, 3600, 0), 20, "linear")
local pega = false
moeda.Touched:Connect(function(outro)
  if pega then return end
  local h = outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid")
  if not h then return end
  local jogador = nil
  for _, j in ipairs(game.Players:GetPlayers()) do if j.Character == outro.Parent then jogador = j end end
  if not jogador then return end
  pega = true
  local stats = jogador:FindFirstChild("leaderstats") or Instance.new("Folder", jogador)
  stats.Name = "leaderstats"
  local moedas = stats:FindFirstChild("Moedas") or Instance.new("IntValue", stats)
  moedas.Name = "Moedas"
  moedas.Value = moedas.Value + 1
  game:GetService("Sons"):Tocar("moeda")
  moeda:Destroy()
end)`);
  } },
  poste: { nome: "💡 Poste de luz", fazer(m, b) {
    peca(m, "Poste", [b.X, b.Y + 4, b.Z], [0.6, 8, 0.6], "#424242", "Metal", { forma: "Cylinder" });
    peca(m, "Lampada", [b.X, b.Y + 8.5, b.Z], [1.6, 1.6, 1.6], "#fff59d", "Neon", { forma: "Ball" });
  } },
};

/** Cria o pronto num Model, apoiado no chão em `base` (posição no chão). Devolve o Model. */
export function colocarPronto(mundo, chave, base, pai = null) {
  const item = PRONTOS[chave];
  if (!item) throw new Error(`Peça pronta desconhecida: ${chave}`);
  const m = criar("Model");
  m.Name = item.nome.replace(/^\S+\s/, "").replace(/\s.*/, "");
  m.Parent = pai || mundo.workspace;
  item.fazer(m, Vector3.de(base));
  return m;
}
