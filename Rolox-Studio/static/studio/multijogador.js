// ROLOX — ver os outros jogadores no mapa (site, /jogar).
//
// A cada ~140 ms manda a minha posição para o site e recebe a dos outros do mesmo
// servidor. Os outros viram personagens "fantasma" (com o avatar de cada um):
// presos no lugar para a física (Anchored) e movidos suavemente entre as
// atualizações (interpolação), com o nome em cima da cabeça.

import * as THREE from "three";
import { criarPersonagem } from "./fisica.js";
import { Vector3 } from "./motor.js";

const INTERVALO_MS = 140;
const SUAVIDADE = 12;          // quanto maior, mais rápido alcança a posição recebida

export class Multijogador {
  constructor({ jogo, render, passe, csrf, camada, url = "/api/sala", aoMudar = () => {} }) {
    this.jogo = jogo;
    this.render = render;
    this.passe = passe;
    this.csrf = csrf;
    this.url = url;
    this.camada = camada;          // elemento onde ficam os nomes
    this.aoMudar = aoMudar;        // (quantidade de outros jogadores) => void
    this.outros = new Map();       // id -> {modelo, raiz, alvo, giro, nome(el)}
    this.enviando = false;
    this.parado = false;
    this.falhas = 0;
  }

  iniciar() {
    this.timer = setInterval(() => this._trocar(), INTERVALO_MS);
    this._sair = () => {
      const f = new FormData(); f.append("passe", this.passe); f.append("csrf", this.csrf);
      navigator.sendBeacon?.(this.url + "/sair", f);
    };
    addEventListener("pagehide", this._sair);
  }

  parar() {
    this.parado = true;
    clearInterval(this.timer);
    removeEventListener("pagehide", this._sair);
    this._sair?.();
    for (const id of [...this.outros.keys()]) this._remover(id);
  }

  _meuEstado() {
    const raiz = this.jogo.local?.raiz;
    if (!raiz) return null;
    const p = raiz.Position, m = this.jogo.local.humanoid.MoveDirection;
    return { passe: this.passe, p: [p.X, p.Y, p.Z], r: raiz._rotY || 0,
             m: !!m && m.Magnitude > 0.05, v: this.jogo.local.humanoid.Health > 0 };
  }

  async _trocar() {
    if (this.enviando || this.parado) return;
    const estado = this._meuEstado();
    if (!estado) return;
    this.enviando = true;
    try {
      const r = await fetch(this.url, {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": this.csrf }, body: JSON.stringify(estado),
      });
      if (!r.ok) throw new Error(String(r.status));
      this.falhas = 0;
      this._aplicar((await r.json()).jogadores || []);
    } catch {
      if (++this.falhas > 25) this._aplicar([]);       // ~3 s sem resposta: some todo mundo
    } finally { this.enviando = false; }
  }

  _aplicar(lista) {
    const vistos = new Set();
    for (const j of lista) {
      vistos.add(j.id);
      let o = this.outros.get(j.id);
      if (!o) o = this._criar(j);
      o.alvo = new Vector3(j.p[0], j.p[1], j.p[2]);
      o.giro = j.r;
      o.vivo = j.v !== false;
    }
    for (const id of [...this.outros.keys()]) if (!vistos.has(id)) this._remover(id);
    this.aoMudar(this.outros.size);
  }

  _criar(j) {
    const p = criarPersonagem(this.jogo.mundo, j.n, j.a || {});
    p.raiz.Anchored = true;                 // quem move é a rede, não a física daqui
    p.raiz._remoto = true;
    p.raiz.Position = new Vector3(j.p[0], j.p[1], j.p[2]);
    p.raiz._rotY = j.r;
    const nome = document.createElement("div");
    nome.className = "nome-jogador";
    nome.textContent = j.n;                // texto puro: nome nunca vira HTML
    this.camada?.appendChild(nome);
    const o = { modelo: p.modelo, raiz: p.raiz, alvo: p.raiz.Position, giro: j.r, nome, vivo: true };
    this.outros.set(j.id, o);
    return o;
  }

  _remover(id) {
    const o = this.outros.get(id);
    if (!o) return;
    o.modelo.Destroy();
    o.nome.remove();
    this.outros.delete(id);
  }

  /** Chamado a cada quadro, antes de jogo.passo(): move os outros suavemente. */
  quadro(dt) {
    const k = 1 - Math.exp(-SUAVIDADE * dt);
    for (const o of this.outros.values()) {
      const a = o.raiz.Position, b = o.alvo;
      const longe = Math.hypot(b.X - a.X, b.Y - a.Y, b.Z - a.Z) > 25;     // renasceu/teleportou: pula direto
      o.raiz.Position = longe ? b : new Vector3(a.X + (b.X - a.X) * k, a.Y + (b.Y - a.Y) * k, a.Z + (b.Z - a.Z) * k);
      let d = o.giro - (o.raiz._rotY || 0);
      d = Math.atan2(Math.sin(d), Math.cos(d));
      o.raiz._rotY = (o.raiz._rotY || 0) + d * k;
    }
  }

  /** Depois de desenhar: põe os nomes em cima das cabeças. */
  nomes() {
    const cam = this.render.camera, tela = this.render.renderer.domElement;
    const w = tela.clientWidth, h = tela.clientHeight;
    const v = this._v || (this._v = new THREE.Vector3());
    for (const o of this.outros.values()) {
      const p = o.raiz.Position;
      v.set(p.X, p.Y + 3.4, p.Z).project(cam);
      const dist = cam.position.distanceTo(new THREE.Vector3(p.X, p.Y, p.Z));
      const visivel = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1 && dist < 120;
      o.nome.style.display = visivel ? "" : "none";
      if (visivel) {
        o.nome.style.transform = `translate(-50%, -100%) translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h}px)`;
        o.nome.style.opacity = o.vivo ? "1" : "0.45";
      }
    }
  }
}
