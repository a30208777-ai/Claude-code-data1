import { test } from "node:test";
import assert from "node:assert/strict";
import { EMOTES, DURACAO_MS, Gestos } from "../static/studio/emotes.js";

test("gesto dura 4 s e só vale da lista", () => {
  let t = 1000;
  const g = new Gestos(() => t);
  assert.equal(g.atual(), null);
  g.fazer("dancar");
  assert.equal(g.atual(), "dancar");
  t += DURACAO_MS - 1; assert.equal(g.atual(), "dancar");
  t += 2; assert.equal(g.atual(), null);
  assert.throws(() => g.fazer("<b>oi</b>"), /desconhecido/);
  assert.equal(Object.keys(EMOTES).length, 8);
});

test("a lista do site (multijogador.py) é a mesma do jogo", async () => {
  const fs = await import("node:fs");
  const py = fs.readFileSync(new URL("../../Rolox-App/flask/multijogador.py", import.meta.url), "utf8");
  const lista = py.match(/EMOTES = \{([^}]*)\}/)[1].match(/"(\w+)"/g).map((x) => x.slice(1, -1)).sort();
  assert.deepEqual(lista, Object.keys(EMOTES).sort());
});
