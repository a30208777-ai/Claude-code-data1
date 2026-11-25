// VISTA — 🗺️ minimapa: o mapa visto de cima, com você (seta) e os outros jogadores (pontos).
// Desenhado num canvas pequeno, 5 vezes por segundo (leve até no celular).

/** Caixa que contém as peças (ignora chão gigante e coisas muito longe). Pura: dá para testar. */
export function limitesDoMapa(pecas, max = 400) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (const p of pecas) {
    const { X, Z } = p.Position, s = p.Size;
    if (Math.abs(X) > max || Math.abs(Z) > max || s.X > max || s.Z > max) continue;
    x0 = Math.min(x0, X - s.X / 2); x1 = Math.max(x1, X + s.X / 2);
    z0 = Math.min(z0, Z - s.Z / 2); z1 = Math.max(z1, Z + s.Z / 2);
  }
  if (!Number.isFinite(x0)) return { x0: -50, z0: -50, lado: 100 };
  const lado = Math.max(40, x1 - x0, z1 - z0) + 8;
  return { x0: (x0 + x1) / 2 - lado / 2, z0: (z0 + z1) / 2 - lado / 2, lado };
}

/** Mundo (x, z) -> pixel do minimapa. */
export function paraTela(lim, tam, x, z) {
  return [((x - lim.x0) / lim.lado) * tam, ((z - lim.z0) / lim.lado) * tam];
}

export function ligarMinimapa(jogo, { botao, canvas, mj = null }) {
  const tam = canvas.width;
  const g = canvas.getContext("2d");
  let lim = null, ultimo = 0, ligado = false;
  const pecas = () => jogo.mundo.partes().filter((p) => !p._visual && !p._personagem && !p._temporaria && p.Transparency < 0.95);
  const desenhar = () => {
    if (!lim) lim = limitesDoMapa(pecas());
    g.clearRect(0, 0, tam, tam);
    g.fillStyle = "#0e0a1ccc"; g.fillRect(0, 0, tam, tam);
    for (const p of pecas()) {
      const [x, y] = paraTela(lim, tam, p.Position.X - p.Size.X / 2, p.Position.Z - p.Size.Z / 2);
      const w = (p.Size.X / lim.lado) * tam, h = (p.Size.Z / lim.lado) * tam;
      g.fillStyle = p.Color.toHex(); g.globalAlpha = p.CanCollide ? 0.9 : 0.4;
      g.fillRect(x, y, Math.max(1, w), Math.max(1, h));
    }
    g.globalAlpha = 1;
    for (const o of mj ? mj.outros.values() : []) {
      const [x, y] = paraTela(lim, tam, o.raiz.Position.X, o.raiz.Position.Z);
      g.fillStyle = o.dn ? "#ffd54f" : "#ff4081";
      g.beginPath(); g.arc(x, y, 3.5, 0, 7); g.fill();
    }
    const eu = jogo.local?.raiz;
    if (eu) {
      const [x, y] = paraTela(lim, tam, eu.Position.X, eu.Position.Z);
      const a = eu._rotY || 0;
      g.save(); g.translate(x, y); g.rotate(-a);          // olhando para -Z (frente) = seta para cima
      g.fillStyle = "#fff"; g.strokeStyle = "#000"; g.lineWidth = 1;
      g.beginPath(); g.moveTo(0, -6); g.lineTo(4.5, 5); g.lineTo(-4.5, 5); g.closePath(); g.fill(); g.stroke();
      g.restore();
    }
  };
  jogo.extras.push({ nomes() { if (ligado && performance.now() - ultimo > 200) { ultimo = performance.now(); desenhar(); } } });
  const mudar = (sim) => {
    ligado = sim; canvas.hidden = !sim; botao.setAttribute("aria-pressed", String(sim));
    try { localStorage.setItem("rolox.minimapa", sim ? "1" : "0"); } catch { /* sem armazenamento */ }
    if (sim) { lim = null; desenhar(); }
  };
  botao.addEventListener("click", () => mudar(!ligado));
  let salvo = "1";
  try { salvo = localStorage.getItem("rolox.minimapa") ?? "1"; } catch { /* idem */ }
  mudar(salvo === "1");
  return { mudar, desenhar };
}
