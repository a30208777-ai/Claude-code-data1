import { test } from "node:test";
import assert from "node:assert/strict";
import { nomeDaFoto } from "../static/studio/foto.js";

test("nome do arquivo da foto é seguro e tem a data", () => {
  const d = new Date(2026, 10, 21, 8, 5, 9);
  assert.equal(nomeDaFoto("Obby da Lava!", d), "rolox-obby-da-lava-20261121-080509.png");
  assert.equal(nomeDaFoto("Ação & Corrida 🚀", d), "rolox-acao-corrida-20261121-080509.png");
  assert.equal(nomeDaFoto("../../etc", d), "rolox-etc-20261121-080509.png");
  assert.equal(nomeDaFoto("", d), "rolox-jogo-20261121-080509.png");
});
test("formato do clipe escolhe o primeiro suportado", async () => {
  const { formatoClipe } = await import("../static/studio/foto.js");
  assert.equal(formatoClipe({ isTypeSupported: (t) => t === "video/mp4" }), "video/mp4");
  assert.equal(formatoClipe(undefined), null);
});
