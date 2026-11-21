import { test } from "node:test";
import assert from "node:assert/strict";
import { mundoInicial, criar, Vector3 } from "../static/studio/motor.js";
import { copiar, colar, temCopia } from "../static/studio/copiar.js";
import { colocarPronto } from "../static/studio/prontos.js";

const memoria = () => { const d = {}; return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = v; } }; };

test("copia um modelo com script de um projeto e cola em outro, ao lado", () => {
  const arm = memoria();
  const a = mundoInicial(), b = mundoInicial();
  assert.equal(temCopia(arm), false);
  assert.throws(() => colar(b.workspace, arm), /Nada copiado/);
  const porta = colocarPronto(a, "porta", new Vector3(10, 0, 0));
  assert.equal(copiar(porta, arm), 4);                 // Model + Porta + Sensor + Script
  const novo = colar(b.workspace, arm);
  assert.equal(novo.ClassName, "Model");
  assert.equal(novo.FindFirstChild("Porta").Position.X, 14);
  assert.ok(novo.FindFirstChild("AbrirPorta").Source.includes("anim:Mover"));
  assert.equal(novo.Parent, b.workspace);
  assert.throws(() => copiar(a.workspace, arm), /Selecione/);
  const solta = criar("Part"); solta.Position = new Vector3(0, 1, 0); solta.Parent = a.workspace;
  copiar(solta, arm);
  assert.deepEqual(colar(b.workspace, arm).Position.toJSON(), [4, 1, 4]);
});
