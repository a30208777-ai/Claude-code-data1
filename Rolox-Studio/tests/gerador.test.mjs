import { test } from "node:test";
import assert from "node:assert/strict";
import { mundoInicial, salvarMundo, MATERIAIS } from "../static/studio/motor.js";
import { TIPOS_MUNDO, MAX_PECAS_GERADAS, gerarMundo, aleatorio } from "../static/studio/gerador.js";

test("cada tipo de mundo gera peças válidas, ancoradas e dentro do limite", () => {
  for (const tipo of Object.keys(TIPOS_MUNDO)) {
    const m = mundoInicial();
    const pasta = gerarMundo(m, tipo, { semente: 42 });
    const pecas = pasta.GetDescendants();
    assert.ok(pecas.length > 20 && pecas.length <= MAX_PECAS_GERADAS, `${tipo}: ${pecas.length}`);
    for (const p of pecas) {
      assert.ok(p.Anchored, `${tipo}: ${p.Name} solta`);
      assert.ok(MATERIAIS.includes(p.Material), `${tipo}: ${p.Material}`);
      assert.ok(p.Position.Z + p.Size.Z / 2 < -10, `${tipo}: ${p.Name} em cima do spawn`);
    }
    assert.equal(pasta.Parent, m.workspace);
    // dá para chegar andando: a ponte (ou o próprio mundo) encosta no chão inicial (borda z = -64)
    const perto = Math.max(...pecas.map((p) => p.Position.Z + p.Size.Z / 2));
    assert.ok(perto >= -64, `${tipo}: mundo solto no vazio (${perto})`);
  }
});

test("mesma semente = mesmo mundo; semente diferente muda", () => {
  const a = salvarMundo((() => { const m = mundoInicial(); gerarMundo(m, "montanhas", { semente: 7 }); return m; })());
  const b = salvarMundo((() => { const m = mundoInicial(); gerarMundo(m, "montanhas", { semente: 7 }); return m; })());
  const c = salvarMundo((() => { const m = mundoInicial(); gerarMundo(m, "montanhas", { semente: 8 }); return m; })());
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
  const r = aleatorio(3); const x = [r(), r(), r()];
  assert.ok(x.every((v) => v >= 0 && v < 1));
});

test("labirinto tem uma única passagem entre todas as salas (árvore), com entrada e chegada", () => {
  const m = mundoInicial();
  const pasta = gerarMundo(m, "labirinto", { semente: 99 });
  const paredes = pasta.GetChildren().filter((p) => p.Name.startsWith("Parede"));
  const N = 9;
  assert.equal(paredes.length, 2 * N * (N + 1) - (N * N - 1) - 2);
  assert.ok(pasta.FindFirstChild("Entrada") && pasta.FindFirstChild("Chegada"));
});

test("tipo desconhecido dá erro claro", () => {
  assert.throws(() => gerarMundo(mundoInicial(), "vulcao"), /desconhecido/);
});
