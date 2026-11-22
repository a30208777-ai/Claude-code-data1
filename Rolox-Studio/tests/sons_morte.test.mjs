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
