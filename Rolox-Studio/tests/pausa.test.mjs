import { test } from "node:test";
import assert from "node:assert/strict";
import { lembrete, textoTempo, lerTempo, somarTempo, hoje } from "../static/studio/pausa.js";

const memoria = () => { const d = {}; return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = v; } }; };

test("lembrete a cada 1 hora, uma vez só", () => {
  assert.equal(lembrete(59, 0), null);
  assert.match(lembrete(60, 0), /1 hora/);
  assert.equal(lembrete(61, 1), null);
  assert.match(lembrete(120, 1), /2 horas/);
});

test("tempo de hoje soma e zera no dia seguinte", () => {
  const m = memoria();
  assert.equal(somarTempo(5, m, "2026-11-21"), 5);
  assert.equal(somarTempo(3, m, "2026-11-21"), 8);
  assert.equal(lerTempo(m, "2026-11-22"), 0);
  assert.equal(textoTempo(75), "1 h 15 min");
  assert.equal(textoTempo(30), "30 min");
  assert.match(hoje(new Date(2026, 10, 21)), /^2026-11-21$/);
});
test("lembrete respeita o intervalo escolhido (0 = desligado)", async () => {
  const { lembrete } = await import("../static/studio/pausa.js");
  assert.equal(lembrete(30, 0, 30) !== null, true);
  assert.equal(lembrete(30, 0, 60), null);
  assert.equal(lembrete(120, 0, 0), null);
});
