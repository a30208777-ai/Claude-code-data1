// Rolox Studio — física simples (caixas alinhadas aos eixos), personagens e Touched.
// Leve o suficiente para o celular: gravidade, colisão com peças, pulo, Touched.

import { BasePart, Color3, Humanoid, Vector3, criar } from "./motor.js";

const caixa = (p) => {
  const s = p.Size, c = p.Position;
  return { min: [c.X - s.X / 2, c.Y - s.Y / 2, c.Z - s.Z / 2], max: [c.X + s.X / 2, c.Y + s.Y / 2, c.Z + s.Z / 2] };
};
const sobrepoe = (a, b, folga = 0) =>
  a.min[0] < b.max[0] + folga && a.max[0] > b.min[0] - folga &&
  a.min[1] < b.max[1] + folga && a.max[1] > b.min[1] - folga &&
  a.min[2] < b.max[2] + folga && a.max[2] > b.min[2] - folga;

/** Cria um personagem em blocos (cores do avatar opcionais) dentro do Workspace. */
export function criarPersonagem(mundo, nome, avatar = {}) {
  const modelo = criar("Model"); modelo.Name = nome; modelo._temporaria = true;
  const raiz = criar("Part"); raiz.Name = "HumanoidRootPart";
  raiz.Size = new Vector3(2, 5, 1); raiz.Transparency = 1; raiz.CanCollide = true;
  raiz._personagem = true; raiz.Parent = modelo;
  const hum = new Humanoid(); hum.Parent = modelo;
  // partes visuais (não colidem; seguem a raiz)
  const visuais = [
    ["Head", [1.2, 1.2, 1.2], [0, 1.9, 0], avatar.pele || "#c68642"],
    ["Torso", [2, 2, 1], [0, 0.3, 0], avatar.camisa || "#1e88e5"],
    ["Left Arm", [0.9, 2, 0.9], [-1.45, 0.3, 0], avatar.camisa || "#1e88e5"],
    ["Right Arm", [0.9, 2, 0.9], [1.45, 0.3, 0], avatar.camisa || "#1e88e5"],
    ["Left Leg", [0.95, 2, 0.95], [-0.5, -1.7, 0], avatar.calca || "#37474f"],
    ["Right Leg", [0.95, 2, 0.95], [0.5, -1.7, 0], avatar.calca || "#37474f"],
  ];
  for (const [n, t, o, cor] of visuais) {
    const p = criar("Part"); p.Name = n; p.Size = Vector3.de(t); p.Color = Color3.fromHex(cor);
    p.CanCollide = false; p.Anchored = true; p._visual = { raiz, offset: Vector3.de(o) }; p.Parent = modelo;
  }
  modelo.PrimaryPart = raiz;
  modelo.Parent = mundo.workspace;
  return { modelo, raiz, humanoid: hum };
}

export class Fisica {
  constructor(mundo) {
    this.mundo = mundo;
    this.toques = new Map();   // parte -> Set(partes tocando)
  }

  /** Um passo de simulação. `entradas`: Map(raiz -> {x, z, pular, giro}) */
  passo(dt, entradas = new Map()) {
    dt = Math.min(dt, 1 / 20);
    const g = this.mundo.workspace.Gravity ?? 196.2;
    const partes = this.mundo.partes();
    const solidas = partes.filter((p) => p.CanCollide && !p._visual);
    const moveis = partes.filter((p) => !p.Anchored && !p._visual);

    for (const p of moveis) {
      const v = p.Velocity;
      let vx = v.X, vy = v.Y - g * dt, vz = v.Z;
      const hum = p._personagem ? p.Parent?.FindFirstChildOfClass("Humanoid") : null;
      if (hum) {
        const e = entradas.get(p) || { x: 0, z: 0, pular: false };
        const dir = new Vector3(e.x, 0, e.z);
        const m = Math.min(1, dir.Magnitude);
        const u = m > 0.01 ? dir.Unit.mul(m) : new Vector3();
        hum.MoveDirection = u;
        if (hum.Health <= 0) { vx = 0; vz = 0; }
        else { vx = u.X * hum.WalkSpeed; vz = u.Z * hum.WalkSpeed; }
        if ((e.pular || hum.Jump) && p._noChao && hum.Health > 0) { vy = hum.JumpPower; hum.Jump = false; }
        if (m > 0.01) p._rotY = Math.atan2(-u.X, -u.Z);
      }
      p._noChao = false;
      let pos = p.Position;
      // move eixo por eixo e resolve colisões
      for (const [eixo, vel] of [[0, vx], [1, vy], [2, vz]]) {
        if (!vel) continue;
        const d = vel * dt;
        pos = new Vector3(pos.X + (eixo === 0 ? d : 0), pos.Y + (eixo === 1 ? d : 0), pos.Z + (eixo === 2 ? d : 0));
        p._pos = pos;
        if (!p.CanCollide) continue;
        const a = caixa(p);
        for (const s of solidas) {
          if (s === p || s.Parent === p.Parent && p._personagem) continue;
          const b = caixa(s);
          if (!sobrepoe(a, b)) continue;
          // degrau baixo: personagem sobe sozinho (até 1.1)
          if (eixo !== 1 && p._personagem && b.max[1] - a.min[1] <= 1.1 && b.max[1] - a.min[1] > 0) {
            pos = new Vector3(pos.X, b.max[1] + p.Size.Y / 2, pos.Z); p._pos = pos; continue;
          }
          const k = ["X", "Y", "Z"][eixo];
          const ajuste = vel > 0 ? b.min[eixo] - p.Size[k] / 2 - 1e-4 : b.max[eixo] + p.Size[k] / 2 + 1e-4;
          pos = new Vector3(eixo === 0 ? ajuste : pos.X, eixo === 1 ? ajuste : pos.Y, eixo === 2 ? ajuste : pos.Z);
          p._pos = pos;
          if (eixo === 1) { if (vel < 0) p._noChao = true; vy = 0; }
          else if (eixo === 0) vx = 0; else vz = 0;
          a.min = caixa(p).min; a.max = caixa(p).max;
        }
      }
      p.Velocity = new Vector3(hum ? 0 : vx, vy, hum ? 0 : vz);
      if (pos.Y < -200) {                         // caiu do mapa
        if (hum) { hum.Health = 0; } else { p.Destroy(); continue; }
      }
      p._mudou("Position");
    }

    // partes visuais seguem a raiz do personagem
    for (const p of partes) {
      if (!p._visual) continue;
      const r = p._visual.raiz, o = p._visual.offset, a = r._rotY || 0;
      const cx = Math.cos(a), sx = Math.sin(a);
      p._pos = new Vector3(r.Position.X + o.X * cx + o.Z * sx, r.Position.Y + o.Y, r.Position.Z - o.X * sx + o.Z * cx);
      p._rot = new Vector3(0, (a * 180) / Math.PI, 0);
      p._mudou("Position");
    }

    this._toques(partes);
  }

  _toques(partes) {
    const ativas = partes.filter((p) => !p._visual && (p.Touched._fns.length || p.TouchEnded._fns.length || !p.Anchored));
    const todas = partes.filter((p) => !p._visual);
    for (const p of ativas) {
      const antes = this.toques.get(p) || new Set();
      const agora = new Set();
      const a = caixa(p);
      for (const o of todas) {
        if (o === p) continue;
        if (p._personagem && o.Parent === p.Parent) continue;
        if (sobrepoe(a, caixa(o), 0.05)) agora.add(o);
      }
      for (const o of agora) if (!antes.has(o)) {
        // Touched avisa a peça com a OUTRA peça (como no estilo conhecido)
        p.Touched.Fire(o);
        if (!ativas.includes(o)) o.Touched.Fire(p);
      }
      for (const o of antes) if (!agora.has(o)) { p.TouchEnded.Fire(o); if (!ativas.includes(o)) o.TouchEnded.Fire(p); }
      this.toques.set(p, agora);
    }
  }

  /** Personagens tocando partes: o personagem dispara Touched nas peças pela raiz. */
}

export function pontoDeNascimento(mundo, indice = 0) {
  const sp = mundo.partes().find((p) => p.ClassName === "SpawnLocation");
  const base = sp ? sp.Position.add(new Vector3(0, sp.Size.Y / 2 + 3, 0)) : new Vector3(0, 5, 0);
  // 0 no centro; os outros (celulares) ao lado: 3, -3, 6, -6, ...
  const lado = indice === 0 ? 0 : (indice % 2 ? 1 : -1) * Math.ceil(indice / 2) * 3;
  return base.add(new Vector3(lado, 0, 0));
}
