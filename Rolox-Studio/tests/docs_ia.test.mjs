// As receitas que vão para a IA (Rolox-App/flask/docs_ia) precisam FUNCIONAR no motor de verdade.
// Aplica o bloco ```acoes de cada receita, roda os LocalScripts em Lua e confere o resultado.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const raiz = fileURLToPath(new URL("..", import.meta.url));
const pastaDocs = `${raiz}../Rolox-App/flask/docs_ia`;
globalThis.window = globalThis;
vm.runInThisContext(fs.readFileSync(`${raiz}static/vendor/fengari/fengari-web.js`, "utf8"));

const { mundoInicial, Player } = await import("../static/studio/motor.js");
const { criarPersonagem } = await import("../static/studio/fisica.js");
const { ExecutorLua, criarApi } = await import("../static/studio/scripts.js");
const { extrairAcoes, aplicarAcoes, acharCaminho } = await import("../static/studio/agente_ia.js");

const docs = Object.fromEntries(fs.readdirSync(pastaDocs).filter((a) => a.endsWith(".md"))
  .map((a) => [a.replace(/\.md$/, ""), fs.readFileSync(`${pastaDocs}/${a}`, "utf8")]));

async function montar(nomeDoc) {
  const mundo = mundoInicial();
  const { acoes, erro } = extrairAcoes(docs[nomeDoc]);
  assert.equal(erro, null, `${nomeDoc}: bloco acoes inválido`);
  await aplicarAcoes(mundo, acoes);
  const jogador = new Player("Teste"); jogador.Parent = mundo.game.Players;
  mundo.game.Players.LocalPlayer = jogador;
  const p = criarPersonagem(mundo, "Teste");
  jogador.Character = p.modelo;
  const erros = [];
  const lua = new ExecutorLua(criarApi(mundo, (t, tipo) => { if (tipo === "erro" || tipo === "aviso") erros.push(t); }));
  for (const s of mundo.scripts().filter((s) => s.ClassName === "LocalScript")) lua.rodar(s, s.CodigoExecutavel);
  const passar = async (seg) => {
    const fim = Date.now() + seg * 1000;
    while (Date.now() < fim) { mundo.game.RunService.Heartbeat.Fire(0.03); lua.passo(); await new Promise((r) => setTimeout(r, 30)); }
  };
  return { mundo, p, lua, erros, passar };
}

test("todos os documentos têm 'palavras:' e blocos acoes válidos", () => {
  for (const [nome, t] of Object.entries(docs)) {
    if (nome === "README") continue;
    assert.match(t.split("\n")[0], /^palavras:/, nome);
    for (const m of t.matchAll(/```acoes\n([\s\S]*?)```/g)) assert.doesNotThrow(() => JSON.parse(m[1]), nome);
  }
});

test("receita da porta: abre ao tocar e fecha sozinha", async () => {
  const { mundo, p, lua, erros, passar } = await montar("porta");
  const porta = acharCaminho(mundo, "Workspace.Porta");
  porta.Touched.Fire(acharCaminho(mundo, "Workspace.Baseplate") || porta);      // não é jogador: nada acontece
  await passar(0.1);
  assert.equal(porta.CanCollide, true);
  porta.Touched.Fire(p.raiz);
  await passar(0.2);
  assert.equal(porta.CanCollide, false);
  assert.equal(porta.Transparency, 0.8);
  lua.fechar();
  assert.deepEqual(erros, []);
});

test("receita das moedas: pega, soma no placar e no Cofre", async () => {
  const { mundo, p, lua, erros, passar } = await montar("moedas_placar");
  const pasta = acharCaminho(mundo, "Workspace.Moedas");
  assert.equal(pasta.GetChildren().length, 3);
  const m1 = pasta.FindFirstChild("Moeda1");
  m1.Touched.Fire(p.raiz); m1.Touched.Fire(p.raiz);
  await passar(0.2);
  assert.equal(pasta.GetChildren().length, 2);
  const stats = mundo.game.Players.LocalPlayer.FindFirstChild("leaderstats");
  assert.equal(stats.FindFirstChild("Moedas").Value, 1);
  assert.equal(mundo.game.Cofre.Ler("total_moedas", 0), 1);
  assert.match(mundo.game.Tela._itens.get("moedas").texto, /🪙 1/);
  lua.fechar();
  assert.deepEqual(erros, []);
});

test("receita do obby: lava mata, chegada dá vitória e emblema", async () => {
  const { mundo, p, lua, erros, passar } = await montar("obby");
  const hum = p.modelo.FindFirstChildOfClass("Humanoid");
  acharCaminho(mundo, "Workspace.Obby.Lava").Touched.Fire(p.raiz);
  await passar(0.1);
  assert.equal(hum.Health, 0);
  acharCaminho(mundo, "Workspace.Obby.Chegada").Touched.Fire(p.raiz);
  await passar(0.1);
  assert.ok(mundo.game.Emblemas.Tem("zerou"));
  lua.fechar();
  assert.deepEqual(erros, []);
});

test("receita da casa: peças no lugar e com vão de porta", async () => {
  const { mundo, lua } = await montar("construcao");
  const casa = acharCaminho(mundo, "Workspace.Casa");
  assert.equal(casa.GetChildren().length, 8);
  const esq = casa.FindFirstChild("FrenteEsq"), dir = casa.FindFirstChild("FrenteDir");
  const vao = (dir.Position.X - dir.Size.X / 2) - (esq.Position.X + esq.Size.X / 2);
  assert.equal(vao, 3);
  lua.fechar();
});

test("receita de animar/efeitos: elevador sobe e botão solta confete", async () => {
  const { mundo, p, lua, erros, passar } = await montar("animar_efeitos");
  const vistos = []; mundo.game.Efeitos.Mostrar.Connect((t) => vistos.push(t));
  mundo.game.Animar._passo(4);
  assert.ok(Math.abs(acharCaminho(mundo, "Workspace.Elevador").Position.Y - 15.5) < 1e-6);
  acharCaminho(mundo, "Workspace.Botao").Touched.Fire(p.raiz);
  await passar(0.1);
  assert.deepEqual(vistos, ["confete"]);
  lua.fechar();
  assert.deepEqual(erros, []);
});

test("receita de materiais/céu: gelo, borracha, neon e pôr do sol", async () => {
  const { mundo, lua } = await montar("materiais_ceu");
  assert.equal(acharCaminho(mundo, "Workspace.PistaGelo").Material, "Gelo");
  assert.equal(acharCaminho(mundo, "Workspace.Trampolim").Material, "Borracha");
  assert.equal(mundo.game.Ceu.Hora, 19);
  lua.fechar();
});
