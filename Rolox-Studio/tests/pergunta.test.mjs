import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const raiz = fileURLToPath(new URL("..", import.meta.url));
globalThis.window = globalThis;
if (!globalThis.fengari) vm.runInThisContext(fs.readFileSync(`${raiz}static/vendor/fengari/fengari-web.js`, "utf8"));
const { mundoInicial, criar } = await import("../static/studio/motor.js");
const { ExecutorLua, criarApi } = await import("../static/studio/scripts.js");

test("💬 tela:Pergunta mostra opções e o script recebe a escolha", () => {
  const m = mundoInicial(), tela = m.game.Tela;
  const vistos = [];
  tela.Mudou.Connect((id, item) => vistos.push([id, item]));
  const saida = [], erros = [];
  const lua = new ExecutorLua(criarApi(m, (t, tipo) => (tipo === "erro" ? erros : saida).push(String(t))));
  const s = criar("LocalScript");
  s.Source = `local tela = game:GetService("Tela")
tela.Respondeu:Connect(function(id, opcao, n) print(id .. "=" .. opcao .. "#" .. n) end)
tela:Pergunta("loja", "Quer a espada?", "Sim", "Não")`;
  lua.rodar(s, s.CodigoExecutavel);
  const [id, item] = vistos.at(-1);
  assert.equal(id, "loja"); assert.equal(item.tipo, "pergunta"); assert.deepEqual(item.opcoes, ["Sim", "Não"]);
  tela._responder("loja", 1);
  assert.deepEqual(saida, ["loja=Não#2"]);
  assert.equal(vistos.at(-1)[1], null);                // a caixa some
  tela._responder("loja", 0);                          // já respondida: nada
  assert.equal(saida.length, 1);
  tela.Pergunta("x", "oi");
  assert.deepEqual(vistos.at(-1)[1].opcoes, ["OK"]);
  tela.Pergunta("y", "?", "a", "b", "c", "d", "e");
  assert.equal(vistos.at(-1)[1].opcoes.length, 4);
  assert.deepEqual(erros, []);
  lua.fechar();
});
