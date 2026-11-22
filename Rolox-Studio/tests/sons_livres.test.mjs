import { test } from "node:test";
import assert from "node:assert/strict";
import { SONS } from "../static/studio/motor.js";

test("todo som da lista tem receita em tela_jogo.js", async () => {
  const fonte = (await import("node:fs")).readFileSync(new URL("../static/studio/tela_jogo.js", import.meta.url), "utf8");
  for (const s of SONS) assert.match(fonte, new RegExp(`\\n  ${s}: \\(a, t\\)`), s);
  assert.ok(SONS.length >= 16);
});
