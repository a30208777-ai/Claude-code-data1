// Os scripts prontos do executor 🤖 (ROLOX Hacks) rodam sem erro no motor de verdade.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const raiz = fileURLToPath(new URL("..", import.meta.url));
globalThis.window = globalThis;
if (!globalThis.fengari) vm.runInThisContext(fs.readFileSync(`${raiz}static/vendor/fengari/fengari-web.js`, "utf8"));
const { mundoInicial, Player, criar } = await import("../static/studio/motor.js");
const { criarPersonagem } = await import("../static/studio/fisica.js");
const { ExecutorLua, criarApi } = await import("../static/studio/scripts.js");
const { SCRIPTS_PRONTOS } = await import("../static/studio/executor.js");

function montar() {
  const m = mundoInicial();
  const j = new Player("Hacker"); j.Parent = m.game.Players; m.game.Players.LocalPlayer = j;
  const p = criarPersonagem(m, "Hacker"); j.Character = p.modelo;
  p.raiz.Position = p.raiz.Position.add({ X: 10, Y: 3, Z: 10 });
  const erros = [], saida = [];
  const lua = new ExecutorLua(criarApi(m, (t, tipo) => (tipo === "erro" ? erros : saida).push(String(t))));
  const rodar = (codigo) => { const s = criar("LocalScript"); s.Name = "Executor"; s.Source = codigo; lua.rodar(s, s.CodigoExecutavel); };
  return { m, p, lua, erros, saida, rodar };
}

test("todos os scripts prontos rodam sem erro", async () => {
  for (const [nome, codigo] of Object.entries(SCRIPTS_PRONTOS)) {
    const { m, lua, erros, rodar } = montar();
    assert.doesNotThrow(() => rodar(codigo), nome);
    for (let i = 0; i < 5; i++) { m.game.RunService.Heartbeat.Fire(0.03); m.game.Animar._passo(0.3); lua.passo(); }
    lua.fechar();
    assert.deepEqual(erros, [], nome);
  }
});

test("os scripts fazem o que prometem", () => {
  const { m, p, lua, saida, rodar } = montar();
  const h = p.modelo.FindFirstChildOfClass("Humanoid");
  rodar(SCRIPTS_PRONTOS["⚡ Velocidade x3"]); assert.equal(h.WalkSpeed, 48);
  rodar(SCRIPTS_PRONTOS["🦘 Super pulo"]); assert.equal(h.JumpPower, 130);
  rodar(SCRIPTS_PRONTOS["🌙 Gravidade da lua"]); assert.equal(m.workspace.Gravity, 40);
  rodar(SCRIPTS_PRONTOS["🏠 Voltar ao spawn"]); assert.ok(Math.abs(p.raiz.Position.X) < 1e-6 && p.raiz.Position.Y > 4);
  rodar(SCRIPTS_PRONTOS["⚽ Chuva de bolas"]);
  const bolas = m.workspace.GetChildren().filter((x) => x.Name.startsWith("BolaHack"));
  assert.equal(bolas.length, 25); assert.ok(bolas.every((b) => !b.Anchored && b.Material === "Borracha"));
  rodar(SCRIPTS_PRONTOS["❤️ Vida infinita"]); h.TakeDamage(30); m.game.RunService.Heartbeat.Fire(0.03); lua.passo();
  assert.equal(h.Health, 100);
  rodar(SCRIPTS_PRONTOS["✈️ Voar"]); assert.equal(m.workspace.Gravity, 0);
  const y = p.raiz.Position.Y; m.game.Tela._clicar("voar_sobe"); lua.passo(); assert.ok(p.raiz.Position.Y > y);
  m.game.Tela._clicar("voar_para"); lua.passo(); assert.equal(m.workspace.Gravity, 196.2);
  rodar(SCRIPTS_PRONTOS["👀 Quem está no jogo"]); assert.ok(saida.some((t) => t.startsWith("Hacker em")));
  rodar("print(1 +)");       // erro de sintaxe vira exceção (o executor mostra na saída)
  lua.fechar();
}, );
