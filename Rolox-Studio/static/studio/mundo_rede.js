// VISTA — mundo compartilhado (modelo do ANFITRIÃO).
//
// Em cada servidor de jogo, um jogador é o anfitrião: o navegador dele roda os Scripts
// (portas, armadilhas, placar...) e manda para os outros o que mudou nas peças. Os outros
// só aplicam (e rodam os LocalScripts deles). O site apenas repassa: nunca roda código
// de ninguém. Se o anfitrião sai, outro assume com o mundo do jeito que estava.
//
// Cada peça do mapa ganha uma CHAVE pela posição na árvore ("w/0/3") — igual em todos os
// aparelhos, porque todos carregam o mesmo mapa. Peças criadas por Script no anfitrião
// ganham chave "n<numero>" e são criadas nos outros.

import { BasePart, Color3, Vector3, criar, materialValido } from "./motor.js";

export const PROPS = ["Position", "Rotation", "Size", "Color", "Transparency", "CanCollide", "Anchored", "Shape", "Material", "Name"];
const CLASSES = new Set(["Part", "SpawnLocation", "Model", "Folder"]);
const MAX_POR_ENVIO = 300;

function deChar(i) {
  for (let p = i; p; p = p._pai) if (p._temporaria || p._personagem || p._visual) return true;
  return false;
}

export function serializar(i, prop) {
  const v = i[prop];
  if (v && typeof v.toJSON === "function") return v.toJSON();
  return typeof v === "number" ? Math.round(v * 1000) / 1000 : v;
}

function aplicarProp(i, prop, v) {
  if (prop === "Position" || prop === "Rotation" || prop === "Size") {
    if (Array.isArray(v) && v.length === 3 && v.every(Number.isFinite)) i[prop] = new Vector3(v[0], v[1], v[2]);
  } else if (prop === "Color") {
    if (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v)) i.Color = Color3.fromHex(v);
  } else if (prop === "Transparency") {
    if (Number.isFinite(v)) i.Transparency = Math.max(0, Math.min(1, v));
  } else if (prop === "CanCollide" || prop === "Anchored") {
    if (typeof v === "boolean") i[prop] = v;
  } else if (prop === "Shape") {
    if (["Block", "Ball", "Cylinder"].includes(v)) i.Shape = v;
  } else if (prop === "Material") {
    if (materialValido(v)) i.Material = v;
  } else if (prop === "Name") {
    if (typeof v === "string" && v.length <= 60) i.Name = v;
  }
}

export class MundoRede {
  constructor(mundo) {
    this.mundo = mundo;
    this.chaveDe = new Map();      // instância -> chave
    this.porChave = new Map();     // chave -> instância
    this.anfitriao = false;
    this.aplicando = false;
    this.sujos = new Map();        // chave -> Set(props)
    this.criados = new Map();      // chave -> {c, p}
    this.destruidos = new Set();
    this.contador = 0;
    this.v = 0;                    // última versão do mundo recebida
  }

  /** Dá chave para tudo que veio do mapa. Chamar ANTES de rodar scripts e criar personagens. */
  indexar() {
    const visitar = (i, chave) => {
      this.chaveDe.set(i, chave); this.porChave.set(chave, i);
      i.GetChildren().filter((f) => !deChar(f)).forEach((f, n) => visitar(f, `${chave}/${n}`));
    };
    visitar(this.mundo.workspace, "w");
    return this.porChave.size;
  }

  _replicavel(i) {
    return (i instanceof BasePart || CLASSES.has(i.ClassName)) && !deChar(i) && i.IsDescendantOf?.(this.mundo.workspace);
  }

  ligar() {
    this.mundo.on("mudou", (i, prop) => {
      if (!this.anfitriao || this.aplicando || !PROPS.includes(prop)) return;
      const k = this.chaveDe.get(i);
      if (!k) return;
      if (!this.sujos.has(k)) this.sujos.set(k, new Set());
      this.sujos.get(k).add(prop);
    });
    this.mundo.on("entrou", (i) => {
      if (!this.anfitriao || this.aplicando || this.chaveDe.has(i) || !CLASSES.has(i.ClassName) || deChar(i)) return;
      if (!i.IsDescendantOf?.(this.mundo.workspace)) return;
      const k = `n${++this.contador}-${Math.random().toString(36).slice(2, 7)}`;
      this.chaveDe.set(i, k); this.porChave.set(k, i);
      this.criados.set(k, { c: i.ClassName });
      this.sujos.set(k, new Set(PROPS));
    });
    this.mundo.on("saiu", (i) => {
      if (!this.anfitriao || this.aplicando) return;
      const k = this.chaveDe.get(i);
      if (!k || k === "w") return;
      this.destruidos.add(k); this.sujos.delete(k); this.criados.delete(k);
    });
  }

  /** Anfitrião: o que mudou desde o último envio. */
  colher() {
    if (!this.anfitriao) return null;
    const m = [];
    for (const [k, props] of this.sujos) {
      if (m.length >= MAX_POR_ENVIO) break;
      const i = this.porChave.get(k);
      this.sujos.delete(k);
      if (!i || i._destruida) continue;
      const item = { k, props: {} };
      const criado = this.criados.get(k);
      if (criado) {
        item.c = criado.c;
        item.p = this.chaveDe.get(i._pai) || "w";
        this.criados.delete(k);
      }
      for (const prop of props) if (prop in i) item.props[prop] = serializar(i, prop);
      m.push(item);
    }
    const d = [...this.destruidos]; this.destruidos.clear();
    return m.length || d.length ? { m, d } : null;
  }

  /** Convidado: aplica o que o anfitrião mandou. */
  aplicar(lista) {
    if (!Array.isArray(lista) || this.anfitriao) return 0;
    this.aplicando = true;
    let n = 0;
    try {
      for (const it of lista) {
        if (!it || typeof it.k !== "string") continue;
        let i = this.porChave.get(it.k);
        if (it.x) {                                         // destruído
          if (i && i !== this.mundo.workspace) { i.Destroy(); this.porChave.delete(it.k); this.chaveDe.delete(i); n++; }
          continue;
        }
        if (!i && CLASSES.has(it.c)) {
          i = criar(it.c);
          i._rede = true;
          this.chaveDe.set(i, it.k); this.porChave.set(it.k, i);
          for (const [prop, v] of Object.entries(it.props || {})) aplicarProp(i, prop, v);
          i.Parent = this.porChave.get(it.p) || this.mundo.workspace;
          n++;
          continue;
        }
        if (!i) continue;
        for (const [prop, v] of Object.entries(it.props || {})) if (PROPS.includes(prop)) aplicarProp(i, prop, v);
        n++;
      }
    } finally { this.aplicando = false; }
    return n;
  }

  /** Convidado: peças do mapa são movidas pela rede, não pela física daqui. */
  modoConvidado() {
    this.anfitriao = false;
    for (const i of this.porChave.values()) if (i instanceof BasePart) i._rede = true;
  }

  /** Virou anfitrião (entrou primeiro ou o anterior saiu). */
  modoAnfitriao() {
    this.anfitriao = true;
    for (const i of this.porChave.values()) i._rede = false;
    // manda o estado de tudo uma vez (quem entrar depois recebe o mundo atual)
    for (const k of this.porChave.keys()) if (k !== "w") this.sujos.set(k, new Set(PROPS));
  }
}
