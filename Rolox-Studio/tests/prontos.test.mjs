// Peças prontas do Studio: aparecem no lugar certo e os scripts delas FUNCIONAM no motor.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const raiz = fileURLToPath(new URL("..", import.meta.url));
globalThis.window = globalThis;
if (!globalThis.fengari) vm.runInThisContext(fs.readFileSync(`${raiz}static/vendor/fengari/fengari-web.js`, "utf8"));
const { mundoInicial, Player, Vector3 } = await import("../static/studio/motor.js");
const { criarPersonagem } = await import("../static/studio/fisica.js");
const { ExecutorLua, criarApi } = await import("../static/studio/scripts.js");
const { PRONTOS, colocarPronto } = await import("../static/studio/prontos.js");

function rodarScripts(m, model) {
  const erros = [];
  const lua = new ExecutorLua(criarApi(m, (t, tipo) => { if (tipo === "erro") erros.push(String(t)); }));
  for (const s of model.GetDescendants().filter((x) => x.ClassName === "Script")) lua.rodar(s, s.CodigoExecutavel);
  return { lua, erros };
}

test("todas as peças prontas aparecem apoiadas no chão e os scripts carregam", () => {
  for (const chave of Object.keys(PRONTOS)) {
    const m = mundoInicial();
    const model = colocarPronto(m, chave, new Vector3(10, 0, -10));
    const pecas = model.GetDescendants().filter((x) => "Position" in x);
    assert.ok(pecas.length >= 1, chave);
    assert.ok(pecas.every((p) => p.Anchored && p.Position.Y - p.Size.Y / 2 >= -0.01), `${chave}: peça enterrada`);
    const { lua, erros } = rodarScripts(m, model);
    lua.fechar();
    assert.deepEqual(erros, [], chave);
  }
});

test("lava mata, moeda dá placar e some, porta abre sozinha", () => {
  const m = mundoInicial();
  const j = new Player("Eu"); j.Parent = m.game.Players; m.game.Players.LocalPlayer = j;
  const p = criarPersonagem(m, "Eu"); j.Character = p.modelo;
  const h = p.modelo.FindFirstChildOfClass("Humanoid");
  const lava = colocarPronto(m, "lava", new Vector3(20, 0, 0));
  const moeda = colocarPronto(m, "moeda", new Vector3(30, 0, 0));
  const porta = colocarPronto(m, "porta", new Vector3(40, 0, 0));
  const scripts = [lava, moeda, porta].map((x) => rodarScripts(m, x));
  moeda.FindFirstChild("Moeda").Touched.Fire(p.raiz);
  assert.equal(j.FindFirstChild("leaderstats").FindFirstChild("Moedas").Value, 1);
  assert.equal(moeda.FindFirstChild("Moeda"), null);
  const y0 = porta.FindFirstChild("Porta").Position.Y;
  porta.FindFirstChild("Sensor").Touched.Fire(p.raiz);
  m.game.Animar._passo(1);
  assert.ok(porta.FindFirstChild("Porta").Position.Y > y0 + 7);
  lava.FindFirstChild("Lava").Touched.Fire(p.raiz);
  assert.equal(h.Health, 0);
  for (const s of scripts) { assert.deepEqual(s.erros, []); s.lua.fechar(); }
});
