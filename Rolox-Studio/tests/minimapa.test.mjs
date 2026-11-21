import { test } from "node:test";
import assert from "node:assert/strict";
import { limitesDoMapa, paraTela } from "../static/studio/minimapa.js";

const P = (x, z, sx, sz) => ({ Position: { X: x, Z: z }, Size: { X: sx, Z: sz } });

test("limites ignoram o chão gigante e enquadram as peças", () => {
  const lim = limitesDoMapa([P(0, 0, 2048, 2048), P(10, 10, 4, 4), P(-30, 20, 4, 4)]);
  assert.ok(lim.lado >= 44 && lim.lado < 60);
  const [x, y] = paraTela(lim, 100, 10, 10);
  assert.ok(x > 0 && x < 100 && y > 0 && y < 100);
  assert.deepEqual(limitesDoMapa([]), { x0: -50, z0: -50, lado: 100 });
});
