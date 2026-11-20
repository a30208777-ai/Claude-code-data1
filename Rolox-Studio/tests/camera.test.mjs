// Testes da câmera do jogador (sem navegador): node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { CameraJogador } from "../static/studio/camera.js";

function renderFalso(parede = Infinity) {
  const pos = { x: 0, y: 0, z: 0, set(x, y, z) { this.x = x; this.y = y; this.z = z; } };
  const olhando = {};
  return {
    camera: { position: pos, lookAt: (x, y, z) => Object.assign(olhando, { x, y, z }) },
    olhando,
    distanciaLivre: (_o, _d, max) => Math.min(max, parede),
  };
}
const dist = (p, f) => Math.hypot(p.x - f.x, p.y - f.y, p.z - f.z);

test("segue o jogador olhando para ele, na distância do zoom", () => {
  const r = renderFalso(), c = new CameraJogador(r, { distancia: 10 });
  c.atualizar({ X: 5, Y: 3, Z: -2 }, 1 / 60);
  assert.deepEqual(r.olhando, { x: 5, y: 4.5, z: -2 });
  assert.ok(Math.abs(dist(r.camera.position, r.olhando) - 10) < 1e-9);
});

test("parede no caminho: a câmera chega perto na hora e volta devagar", () => {
  const r = renderFalso(4), c = new CameraJogador(r, { distancia: 12 });
  c.atualizar({ X: 0, Y: 0, Z: 0 }, 1 / 60);
  assert.ok(dist(r.camera.position, r.olhando) <= 3.6 + 1e-9);
  r.distanciaLivre = (_o, _d, max) => max;           // parede saiu
  c.atualizar({ X: 0, Y: 0, Z: 0 }, 1 / 60);
  const d = dist(r.camera.position, r.olhando);
  assert.ok(d > 3.6 && d < 12, `voltando suave, ficou ${d}`);
});

test("movimento suave, mas teleporte não faz a câmera voar pelo mapa", () => {
  const r = renderFalso(), c = new CameraJogador(r);
  c.atualizar({ X: 0, Y: 0, Z: 0 }, 1 / 60);
  c.atualizar({ X: 1, Y: 0, Z: 0 }, 1 / 60);
  assert.ok(r.olhando.x > 0 && r.olhando.x < 1);
  c.atualizar({ X: 200, Y: 0, Z: 0 }, 1 / 60);
  assert.equal(r.olhando.x, 200);
});

test("zoom no máximo vira primeira pessoa e a inclinação tem limite", () => {
  const r = renderFalso(), c = new CameraJogador(r, { distancia: 0.5 });
  assert.ok(c.primeiraPessoa);
  c.atualizar({ X: 0, Y: 0, Z: 0 }, 1 / 60);
  assert.equal(r.camera.position.y, 1.6);
  c.pitch = 5; c.teclas.add("o");
  for (let i = 0; i < 300; i++) c.atualizar({ X: 0, Y: 0, Z: 0 }, 1 / 30);
  assert.ok(c.distancia <= c.maximo && !c.primeiraPessoa);
});
