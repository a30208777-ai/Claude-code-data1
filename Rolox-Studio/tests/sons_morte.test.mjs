import { test } from "node:test";
import assert from "node:assert/strict";
import { SONS_MORTE, receita, tocarSomMorte } from "../static/studio/sons_morte.js";
import { lerAjustes } from "../static/studio/ajustes.js";

test("todo som (menos nenhum) tem notas", () => {
  for (const k of Object.keys(SONS_MORTE)) assert.equal(receita(k).length > 0, k !== "nenhum", k);
});
test("sem áudio no node não quebra", () => assert.equal(tocarSomMorte("classico"), false));
test("ajuste guarda o som escolhido e ignora inválido", () => {
  const m = (v) => ({ getItem: () => JSON.stringify(v) });
  assert.equal(lerAjustes(m({ somMorte: "sino" })).somMorte, "sino");
  assert.equal(lerAjustes(m({ somMorte: "xx" })).somMorte, "classico");
});
test("sensibilidade da câmera fica entre 0.3 e 3", () => {
  const m = (v) => ({ getItem: () => JSON.stringify(v) });
  assert.equal(lerAjustes(m({ sensibilidade: 9 })).sensibilidade, 3);
  assert.equal(lerAjustes(m({ sensibilidade: 0.5, inverterY: true })).inverterY, true);
  assert.equal(lerAjustes(m({ sensibilidade: "x" })).sensibilidade, 1);
});
test("limite de FPS só aceita 0, 30 ou 60", () => {
  const m = (v) => ({ getItem: () => JSON.stringify(v) });
  assert.equal(lerAjustes(m({ fpsMax: 30 })).fpsMax, 30);
  assert.equal(lerAjustes(m({ fpsMax: 7 })).fpsMax, 0);
});
test("lembrete de pausa só 0, 30 ou 60", () => {
  const m = (v) => ({ getItem: () => JSON.stringify(v) });
  assert.equal(lerAjustes(m({ lembrete: 30 })).lembrete, 30);
  assert.equal(lerAjustes(m({ lembrete: 5 })).lembrete, 60);
  assert.equal(lerAjustes(m({ lembrete: 0 })).lembrete, 0);
});
test("lista de controles tem andar e pular", async () => {
  const { CONTROLES } = await import("../static/studio/ajustes.js");
  const t = CONTROLES.map((c) => c[1]).join(" ");
  assert.match(t, /andar/); assert.match(t, /pular/);
});
