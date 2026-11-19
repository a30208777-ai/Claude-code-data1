// Testes do tradutor Luau -> Lua 5.3 e dos modelos prontos.  Rodar: node --test tests/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { traduzirLuau } from "../static/studio/luau.js";
import { MODELOS } from "../static/studio/modelos.js";

const t = (s) => traduzirLuau(s).replace(/[ \t]+/g, " ").trim();

test("tira tipos de locais, parâmetros, retornos, for e genéricos", () => {
  assert.equal(t("local x: number = 1"), "local x = 1");
  assert.equal(t("local a: string?, b: {number} = 'a', {}"), "local a , b = 'a', {}");
  assert.equal(t("local function f(a: number, b: Vector3?): (number, string) return a end"), "local function f(a , b ) return a end");
  assert.equal(t("for i: number = 1, 3 do end"), "for i = 1, 3 do end");
  assert.equal(t("function obj:metodo<T>(v: T): T return v end"), "function obj:metodo (v ) return v end");
  assert.equal(t("local f = function(...: any) end"), "local f = function(... ) end");
});

test("remove type/export type e asserção ::, mas mantém rótulos ::x::", () => {
  assert.equal(t("type Ponto = { x: number, y: number }\nprint(1)"), "print(1)");
  assert.equal(t("export type Lista<T> = {T}\nprint(1)"), "print(1)");
  assert.equal(t("local v = (x :: number) + 1"), "local v = (x ) + 1");
  assert.equal(t("goto fim ::fim::"), "goto fim ::fim::");
  assert.equal(t("print(type(5))"), "print(type(5))");
});

test("atribuições compostas", () => {
  assert.equal(t("x += 1"), "x = x + (1)");
  assert.equal(t("t.a.b -= f(2) * 3"), "t.a.b = t.a.b - (f(2) * 3)");
  assert.equal(t("lista[i + 1] *= 2"), "lista[i + 1] = lista[i + 1] * (2)");
  assert.equal(t('s ..= "!"'), 's = s .. ("!")');
  assert.equal(t("if ok then n += 1 end"), "if ok then n = n + (1) end");
});

test("strings com crase viram concatenação com __texto", () => {
  assert.equal(t("print(`Olá {nome}!`)"), 'print(("Olá " .. __texto(nome) .. "!"))');
  assert.equal(t("print(`só texto`)"), 'print(("só texto"))');
  assert.equal(t("print(`chave \\{literal} e {a + b}`)"), 'print(("chave {literal} e " .. __texto(a + b)))');
});

test("continue vira goto para o fim do laço certo", () => {
  const lua = traduzirLuau("for i = 1, 3 do\n  if i == 2 then continue end\n  print(i)\nend");
  assert.match(lua, /goto __continue1/);
  assert.match(lua, /::__continue1:: end\s*$/);
  const variavel = traduzirLuau("local continue = 1\ncontinue = continue + 1");
  assert.doesNotMatch(variavel, /goto/);
});

test("mantém o número de linhas (erros apontam a linha certa)", () => {
  const src = "local a: number = 1\ntype X = {\n  y: number\n}\nlocal b = `oi {a}`\nb ..= 'x'\n";
  assert.equal(traduzirLuau(src).split("\n").length, src.split("\n").length);
});

test("modelos prontos: vazio, obby e moedas", () => {
  assert.deepEqual(MODELOS.map((m) => m.id), ["vazio", "obby", "moedas"]);
  const obby = MODELOS[1].criar();
  assert.ok(obby.workspace.Lavas.LavaMovel);
  assert.ok(obby.workspace.Chegada);
  const ls = obby.game.StarterPlayer.StarterPlayerScripts.Obby;
  assert.equal(ls.Linguagem, "lua");
  assert.doesNotThrow(() => traduzirLuau(ls.CodigoExecutavel));
  const moedas = MODELOS[2].criar();
  assert.equal(moedas.workspace.Moedas.GetChildren().length, 10);
  assert.equal(moedas.game.ServerScriptService.Moedas.Linguagem, "python");
});
