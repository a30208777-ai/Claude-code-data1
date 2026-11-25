import { test } from "node:test";
import assert from "node:assert/strict";
import { resumoObj, nomeSemExtensao, TAMANHO_ALVO } from "../static/studio/converter_ia.js";

const OBJ = `o Mesa
usemtl madeira
v 0 0 0
v 2 0 0
v 2 1 1
v 0 1 1
f 1 2 3 4
o Copo
usemtl vidro
v 1 1 0.5
v 1.2 1.4 0.6
v 1.1 1.2 0.7
f 5 6 7`;

test("resumo do .obj: uma linha por parte, na escala do VISTA, chão em y=0", () => {
  const r = resumoObj(OBJ, "mesa.obj");
  assert.equal(r.grupos, 2);
  assert.match(r.texto, /Mesa \| centro \[0,\d+(\.\d)?,0\] \| tamanho \[40,20,20\] \| material "madeira"/);
  assert.match(r.texto, /Copo .*material "vidro"/);
  assert.ok(TAMANHO_ALVO === 40);
});
test(".obj sem faces dá erro claro", () => assert.throws(() => resumoObj("v 0 0 0"), /faces/));
test(".vista, .rolox e .json abrem igual (só o nome muda)", () => {
  assert.equal(nomeSemExtensao("castelo.vista"), "castelo");
  assert.equal(nomeSemExtensao("castelo.rolox"), "castelo");
  assert.equal(nomeSemExtensao("meu mapa.json"), "meu_mapa");
});
