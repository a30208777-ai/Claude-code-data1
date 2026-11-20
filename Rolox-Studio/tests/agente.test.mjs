// Testes da IA que mexe no Studio (sem navegador): node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { mundoInicial } from "../static/studio/motor.js";
import { extrairAcoes, aplicarAcoes, acharCaminho, resumoCena } from "../static/studio/agente_ia.js";

const RESPOSTA = `Pronto! Criei a porta e o script que abre ela.
\`\`\`acoes
[
  {"acao": "criar", "classe": "Part", "nome": "Porta", "posicao": [0, 3, -10], "tamanho": [4, 6, 1], "cor": "#8d6e63"},
  {"acao": "criar", "classe": "LocalScript", "nome": "AbrirPorta", "linguagem": "lua",
   "codigo": "local porta = workspace.Porta\\nporta.Touched:Connect(function()\\n  porta.Transparency = 0.8\\n  porta.CanCollide = false\\nend)"}
]
\`\`\`
Toque na porta para abrir.`;

test("extrai as ações e deixa o texto limpo", () => {
  const { acoes, texto, erro } = extrairAcoes(RESPOSTA);
  assert.equal(acoes.length, 2);
  assert.equal(erro, null);
  assert.ok(!texto.includes("```") && texto.includes("Toque na porta"));
  assert.ok(extrairAcoes("```acoes\n[{quebrado\n```").erro);
});

test("a IA cria a porta e o LocalScript sozinha (e não duplica na 2ª vez)", async () => {
  const m = mundoInicial();
  assert.equal(acharCaminho(m, "Workspace.Porta"), null);
  const { log } = await aplicarAcoes(m, extrairAcoes(RESPOSTA).acoes);
  const porta = acharCaminho(m, "Workspace.Porta");
  assert.ok(porta && porta.Anchored && porta.Size.Y === 6 && porta.Position.Z === -10);
  const s = acharCaminho(m, "StarterPlayerScripts.AbrirPorta");
  assert.equal(s.ClassName, "LocalScript");
  assert.equal(s.Linguagem, "lua");
  assert.ok(s.CodigoExecutavel.includes("porta.CanCollide = false"));
  assert.ok(log.every((l) => l.startsWith("✅")), log.join(" | "));
  const r2 = await aplicarAcoes(m, extrairAcoes(RESPOSTA).acoes);
  assert.ok(r2.log[0].startsWith("✏️"));
  assert.equal(m.workspace.GetChildren().filter((c) => c.Name === "Porta").length, 1);
});

test("editar, e apagar só com permissão", async () => {
  const m = mundoInicial();
  await aplicarAcoes(m, [{ acao: "criar", classe: "Part", nome: "Bloco" }]);
  await aplicarAcoes(m, [{ acao: "editar", alvo: "Workspace.Bloco", cor: [255, 0, 0], transparencia: 5, forma: "Ball" }]);
  const b = acharCaminho(m, "Workspace.Bloco");
  assert.equal(b.Transparency, 1); assert.equal(b.Shape, "Ball");
  let r = await aplicarAcoes(m, [{ acao: "apagar", alvo: "Workspace.Bloco" }], { confirmar: async () => false });
  assert.ok(acharCaminho(m, "Workspace.Bloco") && r.log[0].startsWith("🚫"));
  r = await aplicarAcoes(m, [{ acao: "apagar", alvo: "Workspace.Bloco" }], { confirmar: async () => true });
  assert.equal(acharCaminho(m, "Workspace.Bloco"), null);
  r = await aplicarAcoes(m, [{ acao: "apagar", alvo: "Workspace" }], { confirmar: async () => true });
  assert.ok(m.workspace && r.log[0].startsWith("❌"));
});

test("recusa coisa perigosa ou maluca", async () => {
  const m = mundoInicial();
  const { log } = await aplicarAcoes(m, [
    { acao: "criar", classe: "Humanoid" },
    { acao: "criar", classe: "Part", nome: "a.b", posicao: [1e9, "x", NaN] },
    { acao: "formatar_disco" },
    null,
  ]);
  assert.ok(log[0].startsWith("❌") && log[2].startsWith("❌"));
  const p = acharCaminho(m, "Workspace.Part");
  assert.equal(p.Position.X, 2000); assert.equal(p.Position.Y, 0);
  const muitas = Array.from({ length: 100 }, () => ({ acao: "criar", classe: "Folder" }));
  assert.equal(extrairAcoes("```acoes\n" + JSON.stringify(muitas) + "\n```").acoes.length, 60);
  const cheio = await aplicarAcoes(m, [{ acao: "criar", classe: "Part", nome: "X" }], { limitePartes: 0 });
  assert.ok(cheio.log[0].includes("limite"));
});

test("resumo do mapa mostra o que existe", async () => {
  const m = mundoInicial();
  await aplicarAcoes(m, extrairAcoes(RESPOSTA).acoes);
  const r = resumoCena(m);
  assert.ok(r.includes("Porta [Part] pos=(0, 3, -10)") && r.includes("AbrirPorta [LocalScript] lua"));
});
