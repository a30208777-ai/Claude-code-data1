// VISTA Studio — 🏝️ gerador de mundo: cria um cenário pronto com peças e materiais do VISTA.
//   ilha · montanhas · labirinto · cidade        (mesma semente = mesmo mundo)
// Tudo vai para uma pasta no Workspace, longe do spawn, e cabe no limite de peças do Studio leve.

import { Color3, Vector3, criar } from "./motor.js";

export const TIPOS_MUNDO = {
  ilha: { nome: "🏝️ Ilha", descricao: "Praia, grama, água em volta e árvores" },
  montanhas: { nome: "⛰️ Montanhas", descricao: "Morros de grama e pedra com neve no topo" },
  labirinto: { nome: "🧩 Labirinto", descricao: "Paredes de tijolo, entrada e chegada de neon" },
  cidade: { nome: "🏙️ Cidade", descricao: "Ruas de concreto e prédios de vidro" },
};
export const MAX_PECAS_GERADAS = 220;

/** Números "aleatórios" que se repetem com a mesma semente. */
export function aleatorio(semente = 1) {
  let s = (Math.abs(Math.floor(semente)) || 1) >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function peca(pasta, nome, pos, tam, cor, material, extra = {}) {
  const p = criar("Part");
  p.Name = nome;
  p.Anchored = true;
  p.Size = new Vector3(...tam);
  p.Position = new Vector3(...pos);
  p.Color = Color3.fromHex(cor);
  p.Material = material;
  Object.assign(p, extra);
  p.Parent = pasta;
  return p;
}

function arvore(pasta, n, x, z, chao, r) {
  const alt = 5 + Math.floor(r() * 4);
  peca(pasta, `Tronco${n}`, [x, chao + alt / 2, z], [1.4, alt, 1.4], "#6d4c41", "Madeira", { Shape: "Cylinder" });
  const copa = 5 + r() * 2;
  peca(pasta, `Copa${n}`, [x, chao + alt + copa / 2 - 1, z], [copa, copa, copa], ["#2e7d32", "#388e3c", "#43a047"][n % 3], "Grama", { Shape: "Ball" });
}

const GERADORES = {
  ilha(pasta, r, c) {
    peca(pasta, "Mar", [c.X, 0.2, c.Z], [100, 0.4, 100], "#1e88e5", "Agua", { CanCollide: false });
    peca(pasta, "Praia", [c.X, 0.75, c.Z], [70, 1.5, 70], "#ffe082", "Areia", { Shape: "Cylinder" });
    peca(pasta, "Gramado", [c.X, 1.75, c.Z], [52, 1, 52], "#66bb6a", "Grama", { Shape: "Cylinder" });
    peca(pasta, "Morro", [c.X + 6, 4, c.Z - 4], [18, 6, 18], "#558b2f", "Grama", { Shape: "Ball" });
    for (let i = 0; i < 12; i++) {
      const a = r() * Math.PI * 2, d = 8 + r() * 14;
      arvore(pasta, i, c.X + Math.cos(a) * d, c.Z + Math.sin(a) * d, 2.25, r);
    }
    for (let i = 0; i < 6; i++) {
      const a = r() * Math.PI * 2, d = 28 + r() * 4;
      peca(pasta, `Pedra${i}`, [c.X + Math.cos(a) * d, 2, c.Z + Math.sin(a) * d], [2 + r() * 2, 1.5 + r(), 2 + r() * 2], "#9e9e9e", "Pedra", { Shape: "Ball" });
    }
  },
  montanhas(pasta, r, c) {
    const N = 11, L = 8;                          // 11 x 11 colunas de 8 x 8
    const fase = [r() * 6, r() * 6, r() * 6];
    for (let i = 0; i < N; i++) {
      for (let j = 0; j < N; j++) {
        const x = (i - (N - 1) / 2) * L, z = (j - (N - 1) / 2) * L;
        const d = Math.hypot(x, z) / (N * L / 2);
        const h = Math.max(1, Math.round((Math.sin(i * 0.7 + fase[0]) + Math.cos(j * 0.6 + fase[1]) + Math.sin((i + j) * 0.4 + fase[2]) + 2)
          * 5 * (1.2 - d)));
        const [cor, mat] = h > 18 ? ["#fafafa", "Gelo"] : h > 11 ? ["#8d8d8d", "Pedra"] : ["#5b8c3a", "Grama"];
        peca(pasta, `Morro${i}_${j}`, [c.X + x, h / 2, c.Z + z], [L, h, L], cor, mat);
      }
    }
  },
  labirinto(pasta, r, c) {
    const N = 9, L = 8, H = 6;                     // 9 x 9 salas
    const visit = Array.from({ length: N }, () => Array(N).fill(false));
    const paredeL = Array.from({ length: N }, () => Array(N + 1).fill(true));   // paredes verticais (entre colunas)
    const paredeH = Array.from({ length: N + 1 }, () => Array(N).fill(true));   // paredes horizontais (entre linhas)
    const pilha = [[0, 0]]; visit[0][0] = true;
    while (pilha.length) {                          // "caminhada" que abre corredores (sempre tem saída)
      const [i, j] = pilha[pilha.length - 1];
      const viz = [[1, 0], [-1, 0], [0, 1], [0, -1]].map(([a, b]) => [i + a, j + b, a, b])
        .filter(([a, b]) => a >= 0 && b >= 0 && a < N && b < N && !visit[a][b]);
      if (!viz.length) { pilha.pop(); continue; }
      const [a, b, di, dj] = viz[Math.floor(r() * viz.length)];
      if (di) paredeL[j][Math.max(i, a)] = false; else paredeH[Math.max(j, b)][i] = false;
      visit[a][b] = true; pilha.push([a, b]);
    }
    paredeH[0][0] = false; paredeH[N][N - 1] = false;           // entrada e saída
    const x0 = c.X - (N * L) / 2, z0 = c.Z - (N * L) / 2;
    peca(pasta, "Piso", [c.X, 0.25, c.Z], [N * L + 2, 0.5, N * L + 2], "#bdbdbd", "Concreto");
    let n = 0;
    for (let j = 0; j < N; j++) for (let i = 0; i <= N; i++) if (paredeL[j][i])
      peca(pasta, `Parede${n++}`, [x0 + i * L, H / 2 + 0.5, z0 + j * L + L / 2], [1, H, L + 1], "#b71c1c", "Tijolo");
    for (let j = 0; j <= N; j++) for (let i = 0; i < N; i++) if (paredeH[j][i])
      peca(pasta, `Parede${n++}`, [x0 + i * L + L / 2, H / 2 + 0.5, z0 + j * L], [L + 1, H, 1], "#b71c1c", "Tijolo");
    peca(pasta, "Entrada", [x0 + L / 2, 0.6, z0 - 3], [6, 0.2, 4], "#00e676", "Neon");
    peca(pasta, "Chegada", [x0 + (N - 1) * L + L / 2, 0.6, z0 + N * L + 3], [6, 0.2, 4], "#ffd600", "Neon");
  },
  cidade(pasta, r, c) {
    const N = 5, Q = 18, R = 8;                     // 5 x 5 quarteirões, ruas de 8
    const tam = N * Q + (N + 1) * R;
    peca(pasta, "Asfalto", [c.X, 0.2, c.Z], [tam, 0.4, tam], "#424242", "Concreto");
    const ini = -tam / 2 + R;
    const cores = ["#90caf9", "#b0bec5", "#80deea", "#ce93d8", "#ffe082", "#a5d6a7"];
    let n = 0;
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const x = c.X + ini + i * (Q + R) + Q / 2, z = c.Z + ini + j * (Q + R) + Q / 2;
      peca(pasta, `Calcada${n}`, [x, 0.6, z], [Q, 0.4, Q], "#e0e0e0", "Concreto");
      if (r() < 0.18) {                              // praça
        peca(pasta, `Praca${n}`, [x, 0.85, z], [Q - 4, 0.1, Q - 4], "#66bb6a", "Grama");
        arvore(pasta, n, x, z, 0.9, r);
      } else {
        const h = 10 + Math.floor(r() * 40);
        peca(pasta, `Predio${n}`, [x, 0.8 + h / 2, z], [Q - 4, h, Q - 4], cores[n % cores.length], r() < 0.5 ? "Vidro" : "Concreto");
        peca(pasta, `Topo${n}`, [x, 1 + h, z], [Q - 7, 0.6, Q - 7], "#00e5ff", "Neon");
      }
      n++;
    }
  },
};

/** Cria o mundo do `tipo` numa pasta do Workspace. Devolve a pasta. */
export function gerarMundo(mundo, tipo, { semente = Date.now(), centro = new Vector3(0, 0, -110) } = {}) {
  const fazer = GERADORES[tipo];
  if (!fazer) throw new Error(`Tipo de mundo desconhecido: ${tipo}`);
  const pasta = criar("Folder");
  pasta.Name = TIPOS_MUNDO[tipo].nome.replace(/^\S+\s/, "");
  pasta.Parent = mundo.workspace;
  const c = Vector3.de(centro);
  fazer(pasta, aleatorio(semente), c);
  // ponte do chão inicial (borda em z = -64) até a beirada do mundo gerado: dá para ir andando
  const beirada = Math.max(...pasta.GetChildren().map((p) => p.Position.Z + p.Size.Z / 2));
  const borda = -62;
  if (beirada < borda) {
    peca(pasta, "Ponte", [c.X, -0.25, (borda + beirada) / 2 + 1], [6, 0.5, borda - beirada + 4], "#8d6e63", "Madeira");
  }
  return pasta;
}
