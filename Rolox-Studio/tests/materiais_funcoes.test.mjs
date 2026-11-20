// Materiais, Raio, Animar, Céu e Efeitos (sem navegador): node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { criar, mundoInicial, salvarMundo, carregarMundo, Vector3, Color3, MATERIAIS, ESTILOS, Player } from "../static/studio/motor.js";
import { Fisica, criarPersonagem } from "../static/studio/fisica.js";
import { MundoRede } from "../static/studio/mundo_rede.js";
import { aplicarAcoes, resumoCena } from "../static/studio/agente_ia.js";

const peca = (m, nome, props = {}) => {
  const p = criar("Part"); p.Name = nome; p.Anchored = true;
  Object.assign(p, props); p.Parent = m.workspace; return p;
};

test("materiais: nomes sem acento, erro claro e salvos no mapa", () => {
  const m = mundoInicial();
  const p = peca(m, "Lago");
  assert.equal(p.Material, "Plastico");
  p.Material = "água"; assert.equal(p.Material, "Agua");
  p.Material = "MADEIRA"; assert.equal(p.Material, "Madeira");
  assert.throws(() => { p.Material = "Diamante"; }, /Material desconhecido: Diamante/);
  assert.equal(MATERIAIS.length, 15);
  const m2 = carregarMundo(JSON.parse(JSON.stringify(salvarMundo(m))));
  assert.equal(m2.workspace.FindFirstChild("Lago").Material, "Madeira");
  // mapa com material estranho não quebra
  const d = salvarMundo(m); d.servicos.Workspace.find((x) => x.props.Name === "Lago").props.Material = "???";
  assert.equal(carregarMundo(d).workspace.FindFirstChild("Lago").Material, "Plastico");
});

test("materiais passam do anfitrião para os convidados", () => {
  const dados = (() => { const m = mundoInicial(); peca(m, "Chao2"); return salvarMundo(m); })();
  const host = new MundoRede(carregarMundo(dados)), conv = new MundoRede(carregarMundo(dados));
  host.indexar(); conv.indexar(); host.ligar(); conv.ligar(); host.modoAnfitriao(); host.colher(); conv.modoConvidado();
  host.mundo.workspace.FindFirstChild("Chao2").Material = "Gelo";
  conv.aplicar(host.colher().m);
  assert.equal(conv.mundo.workspace.FindFirstChild("Chao2").Material, "Gelo");
});

function andarSobre(material, segundos = 1) {
  const m = mundoInicial();
  m.workspace.FindFirstChild("Chao").Material = material;
  const f = new Fisica(m), p = criarPersonagem(m, "T");
  p.raiz.Position = new Vector3(30, 3, 30);            // longe do SpawnLocation (que é de plástico)
  for (let i = 0; i < 30; i++) f.passo(1 / 60);
  const z0 = p.raiz.Position.Z;
  for (let i = 0; i < 60 * segundos; i++) f.passo(1 / 60, new Map([[p.raiz, { x: 0, z: -1, pular: false }]]));
  const andou = z0 - p.raiz.Position.Z;
  for (let i = 0; i < 30; i++) f.passo(1 / 60, new Map([[p.raiz, { x: 0, z: 0, pular: false }]]));
  return { andou, escorregou: z0 - p.raiz.Position.Z - andou, f, p };
}

test("física dos materiais: areia é devagar, gelo escorrega, borracha pula mais", () => {
  const normal = andarSobre("Plastico"), areia = andarSobre("Areia"), gelo = andarSobre("Gelo");
  assert.ok(Math.abs(normal.andou - 16) < 1, `normal ${normal.andou}`);
  assert.ok(areia.andou < normal.andou * 0.7, `areia ${areia.andou}`);
  assert.ok(gelo.andou < normal.andou, "no gelo demora para acelerar");
  assert.ok(gelo.escorregou > 2 && normal.escorregou < 0.5, `gelo escorregou ${gelo.escorregou}`);
  const alturaDoPulo = (material) => {
    const { f, p } = andarSobre(material, 0);
    f.passo(1 / 60, new Map([[p.raiz, { x: 0, z: 0, pular: true }]]));
    let max = 0;
    for (let i = 0; i < 120; i++) { f.passo(1 / 60); max = Math.max(max, p.raiz.Position.Y); }
    return max;
  };
  assert.ok(alturaDoPulo("Borracha") > alturaDoPulo("Plastico") * 1.8);
});

test("Raio acha a primeira peça e ignora quem pedir", () => {
  const m = mundoInicial();
  const parede = peca(m, "Parede", { Position: new Vector3(0, 3, -10), Size: new Vector3(10, 6, 1) });
  peca(m, "Longe", { Position: new Vector3(0, 3, -30), Size: new Vector3(10, 6, 1) });
  const r = m.workspace.Raio(new Vector3(0, 3, 0), new Vector3(0, 0, -1), 100);
  assert.equal(r.Peca, parede);
  assert.ok(Math.abs(r.Distancia - 9.5) < 1e-6 && Math.abs(r.Posicao.Z + 9.5) < 1e-6);
  assert.equal(m.workspace.Raio(new Vector3(0, 3, 0), new Vector3(0, 0, -1), 5), null);          // curto demais
  assert.equal(m.workspace.Raio(new Vector3(0, 3, 0), new Vector3(0, 0, -1), 100, parede).Peca.Name, "Longe");
  assert.equal(m.workspace.Raio(new Vector3(0, 3, 0), new Vector3(0, 1, 0)), null);               // para cima: nada
});

test("Animar: move, cor, sumir, vai-e-volta e avisa quando termina", () => {
  const m = mundoInicial(), a = m.game.Animar;
  const p = peca(m, "Bloco", { Position: new Vector3(0, 0, 0) });
  const fim = [];
  a.Terminou.Connect((pc, tipo) => fim.push(`${pc.Name}:${tipo}`));
  a.Mover(p, new Vector3(10, 0, 0), 1, "linear");
  a._passo(0.5); assert.ok(Math.abs(p.Position.X - 5) < 1e-6);
  a._passo(0.6); assert.equal(p.Position.X, 10);
  assert.deepEqual(fim, ["Bloco:Mover"]);
  a.Cor(p, Color3.fromRGB(255, 0, 0), 1); a.Sumir(p, 1);
  for (let i = 0; i < 12; i++) a._passo(0.1);
  assert.equal(p.Color.toHex(), "#ff0000"); assert.equal(p.Transparency, 1); assert.equal(p.CanCollide, false);
  a.Aparecer(p, 0.5); a._passo(1); assert.equal(p.Transparency, 0); assert.equal(p.CanCollide, true);
  a.VaiEVolta(p, new Vector3(0, 4, 0), 1, "linear");
  a._passo(1); assert.ok(Math.abs(p.Position.Y - 4) < 1e-6);
  a._passo(1); assert.ok(Math.abs(p.Position.Y) < 1e-6);
  assert.ok(a.Animando(p)); a.Parar(p); assert.ok(!a.Animando(p));
  for (const f of Object.values(ESTILOS)) { assert.ok(Math.abs(f(0)) < 1e-9); assert.ok(Math.abs(f(1) - 1) < 1e-9); }
  assert.throws(() => a.Mover(p, new Vector3(), 1, "doido"), /estilos/);
  p.Destroy(); a.Mover(criar("Part"), new Vector3(), 1); a._passo(0.1);     // peça apagada não quebra
});

test("Céu fica salvo no mapa e tem limites", () => {
  const m = mundoInicial();
  m.game.Ceu.Hora = 30; assert.equal(m.game.Ceu.Hora, 6);
  m.game.Ceu.Hora = 19.5; m.game.Ceu.Neblina = 3; m.game.Ceu.Estrelas = false;
  const c = carregarMundo(JSON.parse(JSON.stringify(salvarMundo(m)))).game.Ceu;
  assert.deepEqual([c.Hora, c.Neblina, c.Estrelas], [19.5, 1, false]);
  assert.match(resumoCena(m), /Ceu: hora 19.5, neblina 1/);
});

test("Efeitos: explosão dá dano pela distância e empurra; confete avisa o desenho", () => {
  const m = mundoInicial(), fx = m.game.Efeitos;
  const perto = criarPersonagem(m, "Perto"), longe = criarPersonagem(m, "Longe");
  perto.raiz.Position = new Vector3(2, 2.5, 0); longe.raiz.Position = new Vector3(40, 2.5, 0);
  const caixa = criar("Part"); caixa.Position = new Vector3(0, 1, 3); caixa.Parent = m.workspace;
  const vistos = []; fx.Mostrar.Connect((t) => vistos.push(t));
  const sons = []; m.game.Sons.Tocou.Connect((t, n) => sons.push(n));
  assert.equal(fx.Explosao(new Vector3(0, 2.5, 0), 10), 1);
  const hp = perto.modelo.FindFirstChildOfClass("Humanoid").Health;
  assert.ok(hp > 0 && hp < 100, `vida ${hp}`);
  assert.equal(longe.modelo.FindFirstChildOfClass("Humanoid").Health, 100);
  assert.ok(caixa.Velocity.Magnitude > 10);
  fx.Confete(new Vector3()); fx.Brilho(caixa, 2);
  assert.deepEqual(vistos, ["explosao", "confete", "brilho"]); assert.deepEqual(sons, ["explosao"]);
});

test("a IA usa material e muda o céu", async () => {
  const m = mundoInicial();
  const { log } = await aplicarAcoes(m, [
    { acao: "criar", classe: "Part", nome: "Piso", material: "Gelo", cor: "#b3e5fc" },
    { acao: "criar", classe: "Part", nome: "X", material: "Ouro" },
    { acao: "ceu", hora: 20, neblina: 0.4 },
  ]);
  assert.equal(m.workspace.Piso.Material, "Gelo");
  assert.equal(m.workspace.X.Material, "Plastico");
  assert.equal(m.game.Ceu.Hora, 20);
  assert.ok(log.some((l) => l.startsWith("🌤️")));
});

test("Lua: Material, Raio, Animar e Efeitos funcionam nos scripts", async () => {
  globalThis.window = globalThis;
  const raiz = fileURLToPath(new URL("..", import.meta.url));
  if (!globalThis.fengari) vm.runInThisContext(fs.readFileSync(`${raiz}static/vendor/fengari/fengari-web.js`, "utf8"));
  const { ExecutorLua, criarApi } = await import("../static/studio/scripts.js");
  const m = mundoInicial();
  peca(m, "Alvo", { Position: new Vector3(0, 3, -10), Size: new Vector3(4, 4, 1) });
  const erros = [], saida = [];
  const lua = new ExecutorLua(criarApi(m, (t, tipo) => (tipo === "erro" ? erros : saida).push(String(t))));
  const s = criar("LocalScript");
  s.Source = `local alvo = workspace.Alvo
alvo.Material = "Neon"
local r = workspace:Raio(Vector3.new(0, 3, 0), Vector3.new(0, 0, -1), 50)
print(r.Peca.Name, r.Distancia, r.Posicao.Z)
print(workspace:Raio(Vector3.new(0, 3, 0), Vector3.new(0, 1, 0)) == nil)
game:GetService("Animar"):Mover(alvo, Vector3.new(0, 3, -20), 1, "linear")
game:GetService("Efeitos"):Confete(alvo.Position)
game:GetService("Ceu").Hora = 21
local ok, err = pcall(function() alvo.Material = "Diamante" end)
print(ok)`;
  s.Parent = m.game.StarterPlayer.StarterPlayerScripts;
  lua.rodar(s, s.CodigoExecutavel);
  assert.deepEqual(erros, []);
  assert.deepEqual(saida, ["Alvo 9.5 -9.5", "true", "false"]);
  assert.equal(m.workspace.Alvo.Material, "Neon");
  m.game.Animar._passo(1);
  assert.equal(m.workspace.Alvo.Position.Z, -20);
  assert.equal(m.game.Ceu.Hora, 21);
  lua.fechar();
});
