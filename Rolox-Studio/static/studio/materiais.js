// ROLOX — aparência dos materiais. As texturas são DESENHADAS na hora (canvas), em tons de cinza:
// a cor da peça continua valendo (a textura só dá o "jeito" de madeira, tijolo, grama...).
// Nada de imagem baixada: leve, sem direito autoral e igual em todo aparelho.

import * as THREE from "three";

// rugosidade, metal, emissivo (brilha sozinho), opacidade mínima, textura
export const ASPECTO = {
  Plastico: { rug: 0.55, metal: 0 },
  Madeira: { rug: 0.85, metal: 0, tex: "madeira" },
  Metal: { rug: 0.35, metal: 0.45, tex: "metal" },   // sem mapa de reflexo: metal alto fica preto
  Grama: { rug: 1, metal: 0, tex: "grama" },
  Pedra: { rug: 0.95, metal: 0, tex: "pedra" },
  Tijolo: { rug: 0.9, metal: 0, tex: "tijolo" },
  Concreto: { rug: 0.95, metal: 0, tex: "concreto" },
  Areia: { rug: 1, metal: 0, tex: "areia" },
  Gelo: { rug: 0.08, metal: 0.1, opac: 0.8, tex: "gelo" },
  Neon: { rug: 0.4, metal: 0, brilho: 1.4 },
  Vidro: { rug: 0.05, metal: 0.2, opac: 0.35 },
  Tecido: { rug: 1, metal: 0, tex: "tecido" },
  Borracha: { rug: 0.98, metal: 0, tex: "borracha" },
  Lava: { rug: 0.7, metal: 0, brilho: 0.9, tex: "lava" },
  Agua: { rug: 0.1, metal: 0.1, opac: 0.6, tex: "agua", anima: true },
};

// gerador pseudoaleatório com semente (a textura sai sempre igual)
function aleatorio(semente) {
  let s = semente >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

const DESENHOS = {
  madeira(c, n, r) {
    c.fillStyle = "#d8d8d8"; c.fillRect(0, 0, n, n);
    for (let y = 0; y < n; y += 1) {
      const onda = Math.sin(y * 0.35 + Math.sin(y * 0.05) * 3) * 0.5 + 0.5;
      c.fillStyle = `rgba(90,90,90,${0.08 + onda * 0.18})`; c.fillRect(0, y, n, 1);
    }
    for (let i = 0; i < n / 8; i++) { c.fillStyle = "rgba(60,60,60,.35)"; c.fillRect(r() * n, r() * n, r() * n * 0.6, 1); }
    c.fillStyle = "rgba(40,40,40,.5)"; c.fillRect(0, 0, n, 1); c.fillRect(0, n / 2, n, 1);   // tábuas
  },
  metal(c, n, r) {
    c.fillStyle = "#e0e0e0"; c.fillRect(0, 0, n, n);
    for (let y = 0; y < n; y++) { c.fillStyle = `rgba(${r() < 0.5 ? "255,255,255" : "120,120,120"},${r() * 0.18})`; c.fillRect(0, y, n, 1); }
    c.strokeStyle = "rgba(80,80,80,.5)"; c.strokeRect(1, 1, n - 2, n - 2);
    c.fillStyle = "rgba(90,90,90,.7)";
    for (const [x, y] of [[4, 4], [n - 6, 4], [4, n - 6], [n - 6, n - 6]]) c.fillRect(x, y, 2, 2);   // rebites
  },
  grama(c, n, r) {
    c.fillStyle = "#cfcfcf"; c.fillRect(0, 0, n, n);
    for (let i = 0; i < n * 6; i++) {
      const v = 150 + Math.floor(r() * 105); c.fillStyle = `rgb(${v},${v},${v})`;
      c.fillRect(r() * n, r() * n, 1, 2 + r() * 3);
    }
  },
  pedra(c, n, r) {
    c.fillStyle = "#c4c4c4"; c.fillRect(0, 0, n, n);
    for (let i = 0; i < 40; i++) {
      const v = 140 + Math.floor(r() * 100); c.fillStyle = `rgba(${v},${v},${v},.6)`;
      c.beginPath(); c.ellipse(r() * n, r() * n, 3 + r() * n / 6, 3 + r() * n / 8, r() * 3, 0, 7); c.fill();
    }
    c.strokeStyle = "rgba(70,70,70,.35)";
    for (let i = 0; i < 6; i++) { c.beginPath(); c.moveTo(r() * n, r() * n); c.lineTo(r() * n, r() * n); c.stroke(); }
  },
  tijolo(c, n) {
    c.fillStyle = "#e6e6e6"; c.fillRect(0, 0, n, n);                 // massa
    const h = n / 4, w = n / 2;
    for (let lin = 0; lin < 4; lin++) {
      for (let col = -1; col < 3; col++) {
        const x = col * w + (lin % 2 ? w / 2 : 0);
        c.fillStyle = lin % 2 ? "#a8a8a8" : "#b4b4b4";
        c.fillRect(x + 2, lin * h + 2, w - 4, h - 4);
      }
    }
  },
  concreto(c, n, r) {
    c.fillStyle = "#cccccc"; c.fillRect(0, 0, n, n);
    for (let i = 0; i < n * 3; i++) { const v = 150 + Math.floor(r() * 90); c.fillStyle = `rgb(${v},${v},${v})`; c.fillRect(r() * n, r() * n, 1.5, 1.5); }
    c.fillStyle = "rgba(90,90,90,.25)"; c.fillRect(0, 0, n, 1); c.fillRect(0, 0, 1, n);
  },
  areia(c, n, r) {
    c.fillStyle = "#dcdcdc"; c.fillRect(0, 0, n, n);
    for (let i = 0; i < n * 10; i++) { const v = 170 + Math.floor(r() * 85); c.fillStyle = `rgb(${v},${v},${v})`; c.fillRect(r() * n, r() * n, 1, 1); }
    for (let y = 0; y < n; y += 6) { c.fillStyle = "rgba(120,120,120,.12)"; c.fillRect(0, y + Math.sin(y) * 2, n, 2); }
  },
  gelo(c, n, r) {
    c.fillStyle = "#f2f2f2"; c.fillRect(0, 0, n, n);
    c.strokeStyle = "rgba(255,255,255,.9)";
    for (let i = 0; i < 10; i++) { c.beginPath(); const x = r() * n, y = r() * n; c.moveTo(x, y); c.lineTo(x + (r() - 0.5) * n / 2, y + (r() - 0.5) * n / 2); c.stroke(); }
    c.strokeStyle = "rgba(170,170,170,.5)";
    for (let i = 0; i < 6; i++) { c.beginPath(); const x = r() * n, y = r() * n; c.moveTo(x, y); c.lineTo(x + (r() - 0.5) * n / 3, y + (r() - 0.5) * n / 3); c.stroke(); }
  },
  tecido(c, n) {
    c.fillStyle = "#d0d0d0"; c.fillRect(0, 0, n, n);
    for (let i = 0; i < n; i += 2) {
      c.fillStyle = "rgba(255,255,255,.18)"; c.fillRect(i, 0, 1, n);
      c.fillStyle = "rgba(80,80,80,.18)"; c.fillRect(0, i, n, 1);
    }
  },
  borracha(c, n, r) {
    c.fillStyle = "#c8c8c8"; c.fillRect(0, 0, n, n);
    c.fillStyle = "rgba(90,90,90,.35)";
    for (let y = 4; y < n; y += 8) for (let x = 4; x < n; x += 8) { c.beginPath(); c.arc(x + (y % 16 ? 4 : 0), y, 1.6, 0, 7); c.fill(); }
    for (let i = 0; i < n; i++) { c.fillStyle = `rgba(255,255,255,${r() * 0.05})`; c.fillRect(r() * n, r() * n, 2, 2); }
  },
  lava(c, n, r) {
    c.fillStyle = "#ffffff"; c.fillRect(0, 0, n, n);
    c.fillStyle = "#4a4a4a";                                    // crosta escura entre as rachaduras
    for (let i = 0; i < 18; i++) { c.beginPath(); c.ellipse(r() * n, r() * n, 4 + r() * n / 7, 3 + r() * n / 9, r() * 3, 0, 7); c.fill(); }
  },
  agua(c, n) {
    c.fillStyle = "#e8e8e8"; c.fillRect(0, 0, n, n);
    c.strokeStyle = "rgba(255,255,255,.8)"; c.lineWidth = 1.5;
    for (let y = 0; y < n; y += n / 8) {
      c.beginPath();
      for (let x = 0; x <= n; x += 2) c.lineTo(x, y + Math.sin((x / n) * Math.PI * 4) * 2);
      c.stroke();
    }
  },
};

const cacheTex = new Map();
/** Textura base de um material (uma por material e tamanho; as peças usam clones com repetição própria). */
export function texturaBase(nome, pesado) {
  const tipo = ASPECTO[nome]?.tex;
  if (!tipo || typeof document === "undefined") return null;
  const n = pesado ? 128 : 64, chave = `${tipo}:${n}`;
  if (!cacheTex.has(chave)) {
    const canvas = document.createElement("canvas"); canvas.width = canvas.height = n;
    const c = canvas.getContext("2d");
    if (!c) return null;
    DESENHOS[tipo](c, n, aleatorio(tipo.length * 977 + n));
    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    cacheTex.set(chave, t);
  }
  return cacheTex.get(chave);
}

/** Material do Three.js para a peça (cor + material do ROLOX + transparência). */
export function criarMaterial(i, pesado) {
  const a = ASPECTO[i.Material] || ASPECTO.Plastico;
  const m = new THREE.MeshStandardMaterial({ color: i.Color.toHex(), roughness: a.rug, metalness: a.metal });
  const base = texturaBase(i.Material, pesado);
  if (base) { m.map = base.clone(); m.map.needsUpdate = true; }
  if (a.brilho) {
    m.emissive = new THREE.Color(i.Color.toHex());
    m.emissiveIntensity = a.brilho;
    if (m.map && i.Material === "Lava") m.emissiveMap = m.map;
  }
  m.userData.material = i.Material;
  ajustarMaterial(m, i);
  return m;
}

/** Atualiza cor, transparência e repetição da textura (chamado quando a peça muda). */
export function ajustarMaterial(m, i) {
  const a = ASPECTO[m.userData.material] || ASPECTO.Plastico;
  m.color.set(i.Color.toHex());
  if (a.brilho) m.emissive.set(i.Color.toHex());
  const opac = Math.min(1 - i.Transparency, a.opac ?? 1);
  m.transparent = opac < 1;
  m.opacity = opac;
  m.depthWrite = opac > 0.5;
  if (m.map) {
    const s = i.Size, u = Math.max(s.X, s.Z) / 4, v = Math.max(s.Y, Math.min(s.X, s.Z)) / 4;
    m.map.repeat.set(Math.max(0.25, u), Math.max(0.25, v));
  }
}

// ------------------------------------------------------------------ céu
const CORES_CEU = [            // [hora, céu, luz do sol, intensidade]
  [0, "#0b1026", "#3a4a80", 0.15], [5, "#1c2550", "#5a6aa0", 0.25], [6.5, "#f6a96b", "#ffc48a", 0.7],
  [8, "#9fd3ff", "#ffffff", 1], [16, "#9fd3ff", "#ffffff", 1], [18, "#f08a5d", "#ffb07a", 0.65],
  [19.5, "#2a2f5c", "#6a6aa0", 0.3], [24, "#0b1026", "#3a4a80", 0.15],
];
export function corDoCeu(hora) {
  let a = CORES_CEU[0], b = CORES_CEU[CORES_CEU.length - 1];
  for (let k = 0; k < CORES_CEU.length - 1; k++) {
    if (hora >= CORES_CEU[k][0] && hora <= CORES_CEU[k + 1][0]) { a = CORES_CEU[k]; b = CORES_CEU[k + 1]; break; }
  }
  const t = b[0] === a[0] ? 0 : (hora - a[0]) / (b[0] - a[0]);
  const ceu = new THREE.Color(a[1]).lerp(new THREE.Color(b[1]), t);
  const luz = new THREE.Color(a[2]).lerp(new THREE.Color(b[2]), t);
  return { ceu, luz, forca: a[3] + (b[3] - a[3]) * t };
}
