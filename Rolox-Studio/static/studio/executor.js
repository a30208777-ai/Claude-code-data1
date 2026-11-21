// ROLOX Hacks — executor 🤖 de scripts (só nos servidores de hack/mod).
//
// Roda código Lua (Luau) no SEU jogo, com a mesma API dos LocalScripts: game, workspace, Players,
// Tela, Sons, Animar, Efeitos, Raio... Os servidores hack são separados dos jogadores do ROLOX
// (o banco não mistura) e lá não vale recorde, Cofre nem emblema.

import { criar } from "./motor.js";

export const SCRIPTS_PRONTOS = {
  "⚡ Velocidade x3": `local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
h.WalkSpeed = 48
print("Velocidade: " .. h.WalkSpeed)`,
  "🦘 Super pulo": `local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
h.JumpPower = 130
print("Pulo: " .. h.JumpPower)`,
  "🌙 Gravidade da lua": `workspace.Gravity = 40
print("Gravidade: 40 (normal 196.2)")`,
  "✈️ Voar": `local tela = game:GetService("Tela")
local raiz = game.Players.LocalPlayer.Character.HumanoidRootPart
workspace.Gravity = 0
raiz.Velocity = Vector3.new(0, 0, 0)
tela:Botao("voar_sobe", "⬆ Subir", "direita")
tela:Botao("voar_desce", "⬇ Descer", "direita")
tela:Botao("voar_para", "🛬 Pousar", "direita")
tela.Clicado:Connect(function(id)
  if id == "voar_sobe" then raiz.Position = raiz.Position + Vector3.new(0, 6, 0); raiz.Velocity = Vector3.new(0, 0, 0)
  elseif id == "voar_desce" then raiz.Position = raiz.Position - Vector3.new(0, 6, 0); raiz.Velocity = Vector3.new(0, 0, 0)
  elseif id == "voar_para" then
    workspace.Gravity = 196.2
    tela:Remover("voar_sobe"); tela:Remover("voar_desce"); tela:Remover("voar_para")
  end
end)
print("Voando! Use os botões da direita.")`,
  "❤️ Vida infinita": `local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
game:GetService("RunService").Heartbeat:Connect(function()
  if h.Health > 0 and h.Health < h.MaxHealth then h.Health = h.MaxHealth end
end)
print("Vida infinita ligada")`,
  "🏠 Voltar ao spawn": `local raiz = game.Players.LocalPlayer.Character.HumanoidRootPart
for _, p in ipairs(workspace:GetDescendants()) do
  if p.ClassName == "SpawnLocation" then
    raiz.Position = p.Position + Vector3.new(0, 5, 0)
    raiz.Velocity = Vector3.new(0, 0, 0)
    print("Teleportado para " .. p.Name)
    return
  end
end
print("Este mapa não tem SpawnLocation")`,
  "🌈 Mapa arco-íris": `local anim = game:GetService("Animar")
local n = 0
for _, p in ipairs(workspace:GetDescendants()) do
  if p:IsA("BasePart") and not (p.Parent and p.Parent:FindFirstChildOfClass("Humanoid")) then
    anim:Cor(p, Color3.fromRGB(math.random(0, 255), math.random(0, 255), math.random(0, 255)), 1)
    n = n + 1
  end
end
print(n .. " peças pintadas")`,
  "⚽ Chuva de bolas": `local raiz = game.Players.LocalPlayer.Character.HumanoidRootPart
for i = 1, 25 do
  local b = Instance.new("Part", workspace)
  b.Name = "BolaHack" .. i
  b.Shape = "Ball"
  b.Material = "Borracha"
  b.Size = Vector3.new(2, 2, 2)
  b.Color = Color3.fromRGB(math.random(0, 255), math.random(0, 255), math.random(0, 255))
  b.Position = raiz.Position + Vector3.new(math.random(-12, 12), 25 + i, math.random(-12, 12))
  b.Anchored = false
end
print("25 bolas!")`,
  "💥 Explosão na frente": `local ch = game.Players.LocalPlayer.Character
local frente = ch:FindFirstChildOfClass("Humanoid").MoveDirection
if frente.Magnitude < 0.1 then frente = Vector3.new(0, 0, -1) end
game:GetService("Efeitos"):Explosao(ch.HumanoidRootPart.Position + frente * 12, 10)
print("BUM!")`,
  "🧱 Torre na frente": `local raiz = game.Players.LocalPlayer.Character.HumanoidRootPart
local base = raiz.Position + Vector3.new(0, -2, -8)
for i = 0, 9 do
  local p = Instance.new("Part", workspace)
  p.Name = "TorreHack" .. i
  p.Size = Vector3.new(4, 1, 4)
  p.Position = base + Vector3.new(0, i * 1.2, -i * 3)
  p.Material = "Neon"
  p.Color = Color3.fromRGB(255, 145, 0)
  p.Anchored = true
end
print("Escada de 10 degraus criada")`,
  "🎉 Festa": `local fx = game:GetService("Efeitos")
local raiz = game.Players.LocalPlayer.Character.HumanoidRootPart
game:GetService("Sons"):Musica("acao")
for i = 1, 8 do
  fx:Confete(raiz.Position + Vector3.new(0, 6, 0))
  wait(0.7)
end
game:GetService("Sons"):Musica("")`,
  "👀 Quem está no jogo": `for _, j in ipairs(game.Players:GetPlayers()) do
  local raiz = j.Character and j.Character:FindFirstChild("HumanoidRootPart")
  print(j.Name .. (raiz and (" em " .. tostring(raiz.Position)) or ""))
end`,
};

const GUARDADO = "rolox.executor.script";
const el = (tag, props = {}, ...filhos) => { const e = Object.assign(document.createElement(tag), props); e.append(...filhos); return e; };

/** Liga o botão 🤖 ao painel do executor. Devolve { saida(texto, tipo, nome), rodar(codigo) }. */
export function ligarExecutor(jogo, { botao, painel }) {
  const log = el("div", { className: "exec-log", role: "log", ariaLive: "polite" });
  const area = el("textarea", { className: "exec-codigo", spellcheck: false, rows: 9, ariaLabel: "Script Lua" });
  try { area.value = localStorage.getItem(GUARDADO) || SCRIPTS_PRONTOS["⚡ Velocidade x3"]; }
  catch { area.value = SCRIPTS_PRONTOS["⚡ Velocidade x3"]; }
  const prontos = el("select", { className: "exec-prontos", ariaLabel: "Scripts prontos" },
    el("option", { value: "", textContent: "📜 Scripts prontos..." }),
    ...Object.keys(SCRIPTS_PRONTOS).map((n) => el("option", { value: n, textContent: n })));
  const executar = el("button", { className: "btn pequeno", type: "button", textContent: "▶ Executar" });
  const limpar = el("button", { className: "btn pequeno contorno", type: "button", textContent: "🧹 Limpar saída" });
  const fechar = el("button", { className: "btn-jogo pequeno", type: "button", textContent: "✕", ariaLabel: "Fechar executor" });
  painel.replaceChildren(
    el("div", { className: "exec-topo" }, el("b", { textContent: "🤖 Executor" }), el("span", { className: "exec-nota", textContent: "Lua · só em servidor hack" }), fechar),
    prontos, area, el("div", { className: "exec-botoes" }, executar, limpar), log);

  const escrever = (texto, tipo = "info") => {
    const linha = el("div", { className: `exec-linha ${tipo}`, textContent: texto });
    log.append(linha);
    while (log.children.length > 200) log.firstChild.remove();
    log.scrollTop = log.scrollHeight;
  };
  const rodar = (codigo) => {
    const s = criar("LocalScript");
    s.Name = "Executor";
    s.Source = String(codigo).slice(0, 20000);           // LocalScript já é Lua (sem linha extra: o nº da linha do erro bate)
    try {
      jogo.lua.rodar(s, s.CodigoExecutavel);
      return true;
    } catch (e) {
      escrever(`❌ ${String(e.message || e).replace(/^\[string "[^"]*"\]:/, "linha ")}`, "erro");
      return false;
    }
  };
  executar.addEventListener("click", () => {
    try { localStorage.setItem(GUARDADO, area.value); } catch { /* sem armazenamento */ }
    escrever(`▶ executando (${area.value.split("\n").length} linhas)`, "sistema");
    rodar(area.value);
  });
  limpar.addEventListener("click", () => log.replaceChildren());
  prontos.addEventListener("change", () => { if (prontos.value) { area.value = SCRIPTS_PRONTOS[prontos.value]; prontos.value = ""; } });
  // teclas digitadas no executor não andam com o personagem
  area.addEventListener("keydown", (e) => { e.stopPropagation(); if ((e.ctrlKey || e.metaKey) && e.key === "Enter") executar.click(); });
  const abrir = (sim) => { painel.hidden = !sim; botao.setAttribute("aria-expanded", String(sim)); if (sim) area.focus(); };
  botao.addEventListener("click", () => abrir(painel.hidden));
  fechar.addEventListener("click", () => abrir(false));
  return {
    saida: (texto, tipo, nome) => { if (nome === "Executor" || tipo === "erro") escrever(String(texto), tipo === "erro" ? "erro" : "info"); },
    rodar,
  };
}
