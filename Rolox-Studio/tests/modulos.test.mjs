// Todo módulo do jogo/Studio precisa ser JS válido: um erro de sintaxe derruba a página inteira
// (no celular o painel do dono não abria e o joystick sumia por causa de um nome repetido em dono.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const pasta = fileURLToPath(new URL("../static/studio/", import.meta.url));

test("todos os módulos de static/studio têm sintaxe válida (como módulo do navegador)", () => {
  const arquivos = fs.readdirSync(pasta).filter((f) => f.endsWith(".js"));
  assert.ok(arquivos.length > 10);
  for (const arq of arquivos) {
    try {
      execFileSync(process.execPath, ["--input-type=module", "--check"], { input: fs.readFileSync(pasta + arq), stdio: "pipe" });
    } catch (e) {
      assert.fail(`${arq}: ${String(e.stderr).split("\n").find((l) => l.includes("Error")) || e.message}`);
    }
  }
});

test("dono.js e executor.js carregam", async () => {
  assert.equal(typeof (await import("../static/studio/dono.js")).ligarPainelDono, "function");
  assert.equal(typeof (await import("../static/studio/executor.js")).ligarExecutor, "function");
});
