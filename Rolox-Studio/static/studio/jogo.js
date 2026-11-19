// Rolox Studio — modo Jogar (teste do jogo dentro do Studio).
// Copia o mundo do editor, cria os personagens, roda os scripts e a física.

import { carregarMundo, salvarMundo, Player, BaseScript } from "./motor.js";
import { Fisica, criarPersonagem, pontoDeNascimento } from "./fisica.js";
import { ExecutorLua, ExecutorPython, carregarPython, criarApi } from "./scripts.js";

export class Jogo {
  constructor({ mundoEditor, render, saida, nomeJogador = "Jogador1", controlesExtras = () => [] }) {
    this.saida = saida;
    this.render = render;
    this.mundo = carregarMundo(salvarMundo(mundoEditor));   // cópia: parar volta ao que estava
    this.fisica = new Fisica(this.mundo);
    this.entradas = new Map();      // raiz do personagem -> {x, z, pular}
    this.teclas = new Set();
    this.toque = { x: 0, z: 0, pular: false };
    this.controlesExtras = controlesExtras;
    this.personagensExtras = new Map();   // id do celular -> personagem
    this.nomeJogador = nomeJogador;
    this.rodando = false;
  }

  async iniciar() {
    const m = this.mundo;
    this.render.definirMundo(m);
    const players = m.game.Players;
    const local = new Player(this.nomeJogador); local.Parent = players;
    players.LocalPlayer = local;
    this.local = this._spawn(local, 0);
    players.PlayerAdded.Fire(local);

    const api = criarApi(m, this.saida);
    this.lua = new ExecutorLua(api);
    const scripts = m.scripts().filter((s) => !s.Disabled && s.ClassName !== "ModuleScript");
    const servidor = scripts.filter((s) => s.ClassName === "Script");
    const cliente = scripts.filter((s) => s.ClassName === "LocalScript");
    const precisaPython = m.scripts().some((s) => s.Linguagem === "python");
    if (precisaPython) {
      try { this.python = new ExecutorPython(await carregarPython(this.saida), api); }
      catch (e) { this.saida(`Não foi possível carregar o Python: ${e.message}`, "erro"); }
    }
    this.rodando = true;
    for (const s of [...servidor, ...cliente]) this._rodarScript(s);
    this.ultimo = performance.now();
  }

  _spawn(player, indice) {
    const p = criarPersonagem(this.mundo, player.Name);
    p.raiz.Position = pontoDeNascimento(this.mundo, indice);
    player.Character = p.modelo;
    player.CharacterAdded.Fire(p.modelo);
    return p;
  }

  _rodarScript(s) {
    const lang = s.Linguagem;
    try {
      if (lang === "lua") this.lua.rodar(s, s.CodigoExecutavel);
      else if (this.python) this.python.rodar(s, s.CodigoExecutavel);
      else this.saida(`${s.Name}: Python indisponível`, "erro");
    } catch (e) { this.saida(`${s.Name}: ${e.message}`, "erro"); }
  }

  /** Celulares conectados (PCtoCelular) viram jogadores extras. */
  _sincronizarCelulares() {
    const lista = this.controlesExtras();
    const ids = new Set(lista.map((c) => c.id));
    for (const [id, p] of this.personagensExtras) {
      if (!ids.has(id)) { p.modelo.Destroy(); p.player.Destroy(); this.personagensExtras.delete(id); }
    }
    lista.forEach((c, i) => {
      if (!this.personagensExtras.has(c.id)) {
        const pl = new Player(c.nome); pl.Parent = this.mundo.game.Players;
        const p = this._spawn(pl, i + 1); p.player = pl;
        this.personagensExtras.set(c.id, p);
        this.mundo.game.Players.PlayerAdded.Fire(pl);
      }
      const p = this.personagensExtras.get(c.id);
      this.entradas.set(p.raiz, this._relativoCamera(c.x, c.z, c.pular));
    });
  }

  _relativoCamera(lado, frente, pular) {
    const cam = this.render.camera;
    const yaw = Math.atan2(cam.position.x - this.alvo().X, cam.position.z - this.alvo().Z);
    const s = Math.sin(yaw), c = Math.cos(yaw);
    // frente = -Z da câmera
    return { x: lado * c - frente * s, z: -lado * s - frente * c, pular };
  }

  alvo() { return this.local?.raiz.Position ?? { X: 0, Y: 0, Z: 0 }; }

  passo() {
    if (!this.rodando) return;
    const agora = performance.now();
    const dt = Math.min(0.05, (agora - this.ultimo) / 1000);
    this.ultimo = agora;
    // jogador local: teclado + toque
    const t = this.teclas;
    let lado = (t.has("d") || t.has("arrowright") ? 1 : 0) - (t.has("a") || t.has("arrowleft") ? 1 : 0) + this.toque.x;
    let frente = (t.has("w") || t.has("arrowup") ? 1 : 0) - (t.has("s") || t.has("arrowdown") ? 1 : 0) + this.toque.z;
    this.entradas.set(this.local.raiz, this._relativoCamera(lado, frente, t.has(" ") || this.toque.pular));
    this._sincronizarCelulares();
    this.fisica.passo(dt, this.entradas);
    this.mundo.game.RunService.Heartbeat.Fire(dt);
    try { this.lua.passo(); } catch (e) { this.saida(e.message, "erro"); }
    // respawn de quem morreu
    for (const p of [this.local, ...this.personagensExtras.values()]) {
      const h = p.humanoid;
      if (h.Health <= 0 && !p._renascendo) {
        p._renascendo = true;
        setTimeout(() => {
          if (!this.rodando) return;
          h.Health = h.MaxHealth; p.raiz.Position = pontoDeNascimento(this.mundo, 0);
          p.raiz.Velocity = p.raiz.Velocity.mul(0); p._renascendo = false;
        }, 2000);
      }
    }
    this._camera();
  }

  _camera() {
    const cam = this.render.camera, a = this.alvo();
    this.giro = this.giro ?? 0;
    const dist = 18, alt = 9;
    cam.position.set(a.X + Math.sin(this.giro) * dist, a.Y + alt, a.Z + Math.cos(this.giro) * dist);
    cam.lookAt(a.X, a.Y + 1.5, a.Z);
  }

  parar() {
    this.rodando = false;
    this.python?.parar();
    this.lua?.fechar();
  }
}
