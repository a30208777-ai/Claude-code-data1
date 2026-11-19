// Testes do motor e da física (sem navegador).  Rodar: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  Vector3, Color3, criar, mundoInicial, salvarMundo, carregarMundo, DIRETIVA,
} from "../static/studio/motor.js";
import { Fisica, criarPersonagem, pontoDeNascimento } from "../static/studio/fisica.js";

test("diretiva _++linguagemprogroma++_ e padrões por tipo de script", () => {
  assert.equal(criar("LocalScript").Linguagem, "lua");
  assert.equal(criar("Script").Linguagem, "python");
  assert.equal(criar("ModuleScript").Linguagem, "lua");
  const s = criar("Script");
  s.Source = "-- _++linguagemprogroma++_ = lua\nprint('oi')";
  assert.equal(s.Linguagem, "lua");
  assert.equal(s.CodigoExecutavel.trim(), "print('oi')");
  assert.ok(DIRETIVA.test("  _++linguagemprogroma++_ = Python  "));
});

test("trocar a linguagem troca o exemplo, mas não o código do dono", () => {
  const m = criar("ModuleScript");
  m.definirLinguagem("python");
  assert.match(m.Source, /^_\+\+linguagemprogroma\+\+_ = python\ndef ola/);
  m.Source += "x = 1\n";
  m.definirLinguagem("lua");
  assert.match(m.Source, /^_\+\+linguagemprogroma\+\+_ = lua\ndef ola/);
});

test("filhos pelo nome, FindFirstChild, Clone e Destroy", () => {
  const w = mundoInicial();
  assert.equal(w.workspace.Chao.ClassName, "Part");
  assert.equal(w.workspace.FindFirstChild("SpawnLocation").ClassName, "SpawnLocation");
  const c = w.workspace.Chao.Clone();
  assert.equal(c.Parent, null);
  c.Parent = w.workspace;
  assert.equal(w.contarPartes(), 3);
  c.Destroy();
  assert.equal(w.contarPartes(), 2);
  assert.throws(() => { w.workspace.Parent = w.workspace; });
});

test("salvar e carregar o mundo mantém peças, scripts e malhas", () => {
  const w = mundoInicial();
  const p = criar("Part"); p.Name = "Vermelha"; p.Color = Color3.fromRGB(255, 0, 0); p.Position = new Vector3(1, 2, 3); p.Parent = w.workspace;
  const ls = criar("LocalScript"); ls.Parent = w.game.StarterPlayer.StarterPlayerScripts;
  w.assets.malha1 = { obj: "v 0 0 0", mtl: "", texturas: {} };
  const w2 = carregarMundo(JSON.parse(JSON.stringify(salvarMundo(w, "teste"))));
  assert.equal(w2.workspace.Vermelha.Color.toHex(), "#ff0000");
  assert.equal(w2.workspace.Vermelha.Position.toString(), "1, 2, 3");
  assert.equal(w2.game.StarterPlayer.StarterPlayerScripts.LocalScript.Linguagem, "lua");
  assert.ok(w2.assets.malha1);
  assert.throws(() => carregarMundo({ formato: "outro" }));
});

test("física: personagem cai e para no chão, pula e anda", () => {
  const w = mundoInicial();
  const f = new Fisica(w);
  const p = criarPersonagem(w, "Teste");
  p.raiz.Position = new Vector3(10, 10, 10);
  for (let i = 0; i < 120; i++) f.passo(1 / 60);
  assert.ok(Math.abs(p.raiz.Position.Y - 2.5) < 0.01, `y=${p.raiz.Position.Y}`);   // chão no y=0, altura 5
  const entradas = new Map([[p.raiz, { x: 0, z: -1, pular: true }]]);
  f.passo(1 / 60, entradas);
  assert.ok(p.raiz.Velocity.Y > 0);
  for (let i = 0; i < 60; i++) f.passo(1 / 60, new Map([[p.raiz, { x: 0, z: -1, pular: false }]]));
  assert.ok(p.raiz.Position.Z < 0);
});

test("física: Touched com a outra peça e peça solta cai", () => {
  const w = mundoInicial();
  const f = new Fisica(w);
  const alvo = criar("Part"); alvo.Anchored = true; alvo.CanCollide = false; alvo.Position = new Vector3(20, 2, 20); alvo.Parent = w.workspace;
  const tocou = [];
  alvo.Touched.Connect((o) => tocou.push(o.Name));
  const p = criarPersonagem(w, "Teste");
  p.raiz.Position = new Vector3(20, 2.5, 20);
  f.passo(1 / 60);
  assert.deepEqual(tocou, ["HumanoidRootPart"]);
  const solta = criar("Part"); solta.Anchored = false; solta.Position = new Vector3(-20, 10, -20); solta.Parent = w.workspace;
  for (let i = 0; i < 120; i++) f.passo(1 / 60);
  assert.ok(Math.abs(solta.Position.Y - 0.5) < 0.01);
});

test("ponto de nascimento: o primeiro no centro do Spawn", () => {
  const w = mundoInicial();
  assert.equal(pontoDeNascimento(w, 0).X, 0);
  assert.equal(pontoDeNascimento(w, 1).X, 3);
  assert.equal(pontoDeNascimento(w, 2).X, -3);
});
