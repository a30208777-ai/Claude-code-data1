import { test } from "node:test";
import assert from "node:assert/strict";
import { mundoInicial, criar, Vector3, salvarMundo, carregarMundo } from "../static/studio/motor.js";
import { criarPersonagem } from "../static/studio/fisica.js";
import { Jogo } from "../static/studio/jogo.js";

test("🚩 checkpoint: encostou, renasce nele; apagado, volta ao spawn", () => {
  const m = mundoInicial();
  const cp = criar("Checkpoint"); cp.Name = "Check1"; cp.Position = new Vector3(0, 10, -40); cp.Parent = m.workspace;
  assert.equal(cp.Material, "Neon"); assert.ok(cp.Anchored);
  const p = criarPersonagem(m, "Eu");
  const avisos = [];
  m.game.Tela.Mudou.Connect((id, item) => { if (item?.tipo === "aviso") avisos.push(item.texto); });
  const falso = { mundo: m, local: p };
  Jogo.prototype._ligarCheckpoints.call(falso);
  const spawn = Jogo.prototype._ondeRenascer.call(falso, p);
  assert.ok(Math.abs(spawn.Z) < 1, "antes: renasce no spawn");
  cp.Touched.Fire(criar("Part"));                       // outra peça: nada
  assert.equal(p._checkpoint, undefined);
  cp.Touched.Fire(p.raiz);
  assert.equal(p._checkpoint, cp);
  assert.ok(avisos.some((t) => t.includes("Checkpoint")));
  const r = Jogo.prototype._ondeRenascer.call(falso, p);
  assert.deepEqual([r.X, r.Z], [0, -40]); assert.ok(r.Y > 10);
  cp.Destroy();
  assert.ok(Math.abs(Jogo.prototype._ondeRenascer.call(falso, p).Z) < 1, "apagado: volta ao spawn");
});

test("checkpoint é salvo no mapa", () => {
  const m = mundoInicial();
  const cp = criar("Checkpoint"); cp.Name = "C"; cp.Parent = m.workspace;
  const m2 = carregarMundo(JSON.parse(JSON.stringify(salvarMundo(m))));
  assert.equal(m2.workspace.FindFirstChild("C").ClassName, "Checkpoint");
});
