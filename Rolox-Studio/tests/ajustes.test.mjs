import { test } from "node:test";
import assert from "node:assert/strict";
import { lerAjustes, salvarAjustes, escalaPixels, PADRAO } from "../static/studio/ajustes.js";

const memoria = () => { const d = {}; return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = v; } }; };

test("ajustes salvam e voltam; lixo vira o padrão", () => {
  const m = memoria();
  assert.deepEqual(lerAjustes(m), PADRAO);
  salvarAjustes({ qualidade: "baixa", som: false, nomes: true, fps: true }, m);
  assert.deepEqual(lerAjustes(m), { qualidade: "baixa", som: false, nomes: true, fps: true });
  m.setItem("rolox.ajustes", '{"qualidade":"ultra","som":"sim"}');
  assert.deepEqual(lerAjustes(m), PADRAO);
  m.setItem("rolox.ajustes", "{quebrado");
  assert.deepEqual(lerAjustes(m), PADRAO);
  assert.deepEqual(lerAjustes(null), PADRAO);
});

test("qualidade baixa desenha menos pixels", () => {
  assert.equal(escalaPixels("baixa", 3), 0.6);
  assert.equal(escalaPixels("alta", 3), 2);
  assert.equal(escalaPixels("auto", 3, false), 1);
  assert.equal(escalaPixels("auto", 3, true), 2);
});
