// Rolox Studio — núcleo do motor: instâncias, mundo, eventos e salvamento.
// As mecânicas seguem o estilo conhecido de "árvore de instâncias":
// game > Workspace > Part..., com Name/Parent/ClassName, eventos com :Connect().

export class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.X = +x || 0; this.Y = +y || 0; this.Z = +z || 0; }
  static new(x, y, z) { return new Vector3(x, y, z); }
  static de(v) {
    if (v instanceof Vector3) return v;
    if (v == null) return new Vector3();
    if (Array.isArray(v)) return new Vector3(v[0], v[1], v[2]);
    return new Vector3(v.X ?? v.x ?? 0, v.Y ?? v.y ?? 0, v.Z ?? v.z ?? 0);
  }
  add(o) { o = Vector3.de(o); return new Vector3(this.X + o.X, this.Y + o.Y, this.Z + o.Z); }
  sub(o) { o = Vector3.de(o); return new Vector3(this.X - o.X, this.Y - o.Y, this.Z - o.Z); }
  mul(n) { return typeof n === "number" ? new Vector3(this.X * n, this.Y * n, this.Z * n)
    : new Vector3(this.X * n.X, this.Y * n.Y, this.Z * n.Z); }
  get Magnitude() { return Math.hypot(this.X, this.Y, this.Z); }
  get Unit() { const m = this.Magnitude || 1; return this.mul(1 / m); }
  toString() { return `${+this.X.toFixed(3)}, ${+this.Y.toFixed(3)}, ${+this.Z.toFixed(3)}`; }
  toJSON() { return [this.X, this.Y, this.Z]; }
}

export class Color3 {
  constructor(r = 1, g = 1, b = 1) { this.R = +r; this.G = +g; this.B = +b; }
  static new(r, g, b) { return new Color3(r, g, b); }
  static fromRGB(r, g, b) { return new Color3(r / 255, g / 255, b / 255); }
  static fromHex(h) {
    const n = parseInt(String(h).replace("#", ""), 16) || 0;
    return Color3.fromRGB((n >> 16) & 255, (n >> 8) & 255, n & 255);
  }
  static de(c) {
    if (c instanceof Color3) return c;
    if (typeof c === "string") return Color3.fromHex(c);
    if (Array.isArray(c)) return new Color3(c[0], c[1], c[2]);
    return new Color3(c?.R ?? 1, c?.G ?? 1, c?.B ?? 1);
  }
  toHex() {
    const p = (v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0");
    return `#${p(this.R)}${p(this.G)}${p(this.B)}`;
  }
  toString() { return this.toHex(); }
  toJSON() { return this.toHex(); }
}

// ---------------------------------------------------------------- eventos
let reportarErro = (e) => console.error(e);
export function definirReporteDeErro(fn) { reportarErro = fn; }

// Resultado de um handler: async def do Python (corrotina) ou Promise.
// O Pyodide às vezes já agenda a corrotina e libera o objeto: aí ler .type
// dá "already destroyed", e não há nada a fazer.
function agendarResultado(r) {
  let tipo;
  try { tipo = r.type; } catch { return; }
  if (tipo === "coroutine" && globalThis.__roloxAgendarPy) globalThis.__roloxAgendarPy(r);
  else if (typeof r.then === "function") r.then(null, reportarErro);
}

export class Sinal {
  constructor(nome = "Sinal") { this._nome = nome; this._fns = []; }
  Connect(fn) {
    if (fn && typeof fn.copy === "function") fn = fn.copy();   // função Python (Pyodide): manter viva
    const lista = this._fns;
    const ligacao = { Connected: true, Disconnect() {
      this.Connected = false; const i = lista.indexOf(fn); if (i >= 0) lista.splice(i, 1);
    } };
    lista.push(fn);
    return ligacao;
  }
  Fire(...args) {
    for (const fn of [...this._fns]) {
      try {
        const r = fn(...args);
        if (r && (typeof r === "object" || typeof r === "function")) agendarResultado(r);
      } catch (e) { reportarErro(e); }
    }
  }
  limpar() { this._fns.length = 0; }
}

// --------------------------------------------------------------- instâncias
let proximoId = 1;
const CLASSES = {};

// Acesso a filhos pelo nome (workspace.Chao), como no estilo conhecido.
// Toda instância é um Proxy: se a propriedade não existe, procura um filho com esse nome.
const ACESSO_POR_NOME = {
  get(alvo, k, receptor) {
    if (typeof k !== "string" || k in alvo) return Reflect.get(alvo, k, receptor);
    const filho = alvo._filhos?.find((f) => f._nome === k);
    return filho === undefined ? undefined : filho;
  },
};

export class Instance {
  constructor(nome) {
    this.id = proximoId++;
    this._nome = nome || this.constructor.name;
    this._pai = null;
    this._filhos = [];
    this._mundo = null;
    this.Changed = new Sinal("Changed");
    this.ChildAdded = new Sinal("ChildAdded");
    this.ChildRemoved = new Sinal("ChildRemoved");
    this.Destroying = new Sinal("Destroying");
    return new Proxy(this, ACESSO_POR_NOME);
  }
  static new(classe, pai) { return criar(classe, pai); }
  get ClassName() { return this.constructor.classe || this.constructor.name; }
  get Name() { return this._nome; }
  set Name(v) { this._nome = String(v); this._mudou("Name"); }
  get Parent() { return this._pai; }
  set Parent(p) {
    if (p === this._pai) return;
    if (p && (p === this || p.EhDescendenteDe?.(this))) throw new Error("Parent inválido (criaria um ciclo)");
    const antigo = this._pai;
    if (antigo) {
      antigo._filhos.splice(antigo._filhos.indexOf(this), 1);
      antigo.ChildRemoved.Fire(this);
    }
    this._pai = p || null;
    const mundoNovo = p ? p._mundo : null;
    if (p) p._filhos.push(this);
    this._definirMundo(mundoNovo);
    if (p) p.ChildAdded.Fire(this);
    this._mudou("Parent");
  }
  _definirMundo(m) {
    const antes = this._mundo;
    if (antes === m) { return; }
    if (antes) antes._sair(this);
    this._mundo = m;
    if (m) m._entrar(this);
    for (const f of this._filhos) f._definirMundo(m);
  }
  _mudou(prop) {
    if (this._mundo) this._mundo._aoMudar(this, prop);
    this.Changed.Fire(prop);
  }
  GetChildren() { return [...this._filhos]; }
  GetDescendants() { const r = []; for (const f of this._filhos) r.push(f, ...f.GetDescendants()); return r; }
  FindFirstChild(nome, recursivo = false) {
    for (const f of this._filhos) if (f.Name === nome) return f;
    if (recursivo) for (const f of this._filhos) { const a = f.FindFirstChild(nome, true); if (a) return a; }
    return null;
  }
  FindFirstChildOfClass(c) { return this._filhos.find((f) => f.ClassName === c) || null; }
  WaitForChild(nome) { return this.FindFirstChild(nome); }
  IsA(c) {
    for (let k = this.constructor; k && k !== Object; k = Object.getPrototypeOf(k)) {
      if ((k.classe || k.name) === c) return true;
    }
    return c === "Instance";
  }
  EhDescendenteDe(o) { for (let p = this._pai; p; p = p._pai) if (p === o) return true; return false; }
  IsDescendantOf(o) { return this.EhDescendenteDe(o); }
  GetFullName() { const n = []; for (let p = this; p && p.ClassName !== "DataModel"; p = p._pai) n.unshift(p.Name); return n.join("."); }
  Destroy() {
    this.Destroying.Fire();
    for (const f of [...this._filhos]) f.Destroy();
    this.Parent = null;
    for (const s of [this.Changed, this.ChildAdded, this.ChildRemoved, this.Destroying]) s.limpar();
    this._destruida = true;
  }
  Clone() {
    const c = carregarInstancia(salvarInstancia(this));
    return c;
  }
  // propriedades salvas (cada classe acrescenta as suas)
  static props = ["Name"];
  toString() { return this.Name; }
}

function registrar(classe, nome) { classe.classe = nome; CLASSES[nome] = classe; return classe; }
export function criar(nomeClasse, pai) {
  const C = CLASSES[nomeClasse];
  if (!C || C.naoCriavel) throw new Error(`Classe desconhecida: ${nomeClasse}`);
  const i = new C();
  if (pai) i.Parent = pai;
  return i;
}
export const classesCriaveis = () => Object.keys(CLASSES).filter((k) => !CLASSES[k].naoCriavel);

registrar(class Folder extends Instance {}, "Folder");
registrar(class Model extends Instance {}, "Model");

// Valores (ex.: pasta "leaderstats" dentro do jogador = placar do jogo)
class ValorBase extends Instance {
  constructor(nome) { super(nome); this._valor = 0; }
  get Value() { return this._valor; }
  set Value(v) {
    const n = this._converter(v);
    if (n === this._valor) return;
    this._valor = n; this._mudou("Value");
  }
  _converter(v) { const n = Number(v); return Number.isFinite(n) ? n : 0; }
  static props = ["Name", "Value"];
}
registrar(class IntValue extends ValorBase {
  _converter(v) { const n = Math.trunc(Number(v)); return Number.isFinite(n) ? Math.max(-(2 ** 53), Math.min(2 ** 53, n)) : 0; }
}, "IntValue");
registrar(class NumberValue extends ValorBase {}, "NumberValue");

export class BasePart extends Instance {
  constructor(nome) {
    super(nome);
    this._pos = new Vector3(0, 0.5, 0);
    this._tam = new Vector3(4, 1, 2);
    this._rot = new Vector3(0, 0, 0);
    this._cor = Color3.fromHex("#a3a2a5");
    this.Anchored = false;
    this.CanCollide = true;
    this._transp = 0;
    this.Shape = "Block";
    this.Velocity = new Vector3();
    this.Touched = new Sinal("Touched");
    this.TouchEnded = new Sinal("TouchEnded");
  }
  get Position() { return this._pos; }
  set Position(v) { this._pos = Vector3.de(v); this._mudou("Position"); }
  get Size() { return this._tam; }
  set Size(v) { const s = Vector3.de(v); this._tam = new Vector3(Math.max(0.05, s.X), Math.max(0.05, s.Y), Math.max(0.05, s.Z)); this._mudou("Size"); }
  get Rotation() { return this._rot; }
  set Rotation(v) { this._rot = Vector3.de(v); this._mudou("Rotation"); }
  get Orientation() { return this._rot; }
  set Orientation(v) { this.Rotation = v; }
  get Color() { return this._cor; }
  set Color(v) { this._cor = Color3.de(v); this._mudou("Color"); }
  get BrickColor() { return this._cor; }
  set BrickColor(v) { this.Color = v; }
  get Transparency() { return this._transp; }
  set Transparency(v) { this._transp = Math.min(1, Math.max(0, +v || 0)); this._mudou("Transparency"); }
  Destroy() { this.Touched.limpar(); this.TouchEnded.limpar(); super.Destroy(); }
  static props = ["Name", "Position", "Size", "Rotation", "Color", "Anchored", "CanCollide", "Transparency", "Shape"];
}
registrar(class Part extends BasePart { constructor() { super("Part"); } }, "Part");
registrar(class SpawnLocation extends BasePart {
  constructor() { super("SpawnLocation"); this.Anchored = true; this._tam = new Vector3(6, 1, 6); this._cor = Color3.fromHex("#4caf50"); }
}, "SpawnLocation");
registrar(class MeshPart extends BasePart {
  constructor() { super("MeshPart"); this.MeshId = ""; this.Anchored = true; }
  static props = [...BasePart.props, "MeshId"];
}, "MeshPart");

// ---------------------------------------------------------------- scripts
export const DIRETIVA = /^\s*(?:--|#)?\s*_\+\+linguagemprogroma\+\+_\s*=\s*(lua|python)\s*$/i;

export class BaseScript extends Instance {
  constructor(nome) {
    super(nome);
    const C = this.constructor;
    this.Source = `_++linguagemprogroma++_ = ${C.padrao}\n${C.modelos[C.padrao]}`;
    this.Disabled = false;
  }
  static padrao = "lua";
  static modelos = { lua: "", python: "" };
  static props = ["Name", "Source", "Disabled"];
  /** Linguagem declarada na primeira linha (_++linguagemprogroma++_ = lua/python). */
  get Linguagem() {
    for (const l of String(this.Source).split("\n").slice(0, 3)) {
      const m = l.match(DIRETIVA); if (m) return m[1].toLowerCase();
    }
    return this.constructor.padrao;
  }
  definirLinguagem(lang) {
    // se o código ainda é o exemplo da linguagem antiga, troca pelo exemplo da nova
    const modelos = this.constructor.modelos;
    const atual = this.CodigoExecutavel.trim();
    if (modelos[lang] && Object.values(modelos).some((m) => m.trim() === atual)) {
      this.Source = `_++linguagemprogroma++_ = ${lang}\n${modelos[lang]}`;
      this._mudou("Source");
      return;
    }
    const linhas = String(this.Source).split("\n");
    const i = linhas.slice(0, 3).findIndex((l) => DIRETIVA.test(l));
    const diretiva = `_++linguagemprogroma++_ = ${lang}`;
    if (i >= 0) linhas[i] = diretiva; else linhas.unshift(diretiva);
    this.Source = linhas.join("\n");
    this._mudou("Source");
  }
  /** Código sem a linha da diretiva (para rodar). */
  get CodigoExecutavel() {
    return String(this.Source).split("\n").map((l) => (DIRETIVA.test(l) ? "" : l)).join("\n");
  }
}
registrar(class Script extends BaseScript {
  static padrao = "python";
  static modelos = {
    python: "# Script do servidor\nprint(\"Olá do servidor!\")\n",
    lua: "-- Script do servidor\nprint(\"Olá do servidor!\")\n",
  };
  constructor() { super("Script"); }
}, "Script");
registrar(class LocalScript extends BaseScript {
  static padrao = "lua";
  static modelos = {
    lua: "-- LocalScript (roda no dispositivo do jogador)\nprint(\"Olá, \" .. game.Players.LocalPlayer.Name)\n",
    python: "# LocalScript (roda no dispositivo do jogador)\nprint(\"Olá,\", game.Players.LocalPlayer.Name)\n",
  };
  constructor() { super("LocalScript"); }
}, "LocalScript");
registrar(class ModuleScript extends BaseScript {
  static padrao = "lua";
  static modelos = {
    lua: "local modulo = {}\n\nfunction modulo.ola(nome)\n  return \"Olá, \" .. nome\nend\n\nreturn modulo\n",
    python: "def ola(nome):\n    return \"Olá, \" + nome\n",
  };
  constructor() { super("ModuleScript"); }
}, "ModuleScript");

// --------------------------------------------------------- jogadores
export class Humanoid extends Instance {
  constructor() {
    super("Humanoid");
    this.WalkSpeed = 16; this.JumpPower = 50; this._vida = 100; this.MaxHealth = 100;
    this.MoveDirection = new Vector3(); this.Jump = false;
    this.Died = new Sinal("Died");
  }
  get Health() { return this._vida; }
  set Health(v) {
    const antes = this._vida; this._vida = Math.max(0, Math.min(this.MaxHealth, +v || 0));
    if (antes > 0 && this._vida === 0) this.Died.Fire();
    this._mudou("Health");
  }
  TakeDamage(n) { this.Health = this._vida - (+n || 0); }
  Move(dir) { this.MoveDirection = Vector3.de(dir); }
  static props = ["Name", "WalkSpeed", "JumpPower", "MaxHealth"];
}
registrar(Humanoid, "Humanoid");

export class Player extends Instance {
  constructor(nome) { super(nome || "Jogador"); this.Character = null; this.UserId = 0; this.CharacterAdded = new Sinal("CharacterAdded"); }
  static naoCriavel = true;
}
registrar(Player, "Player");

// ---------------------------------------------------------------- serviços
class Servico extends Instance { static naoCriavel = true; }
registrar(class Workspace extends Servico { constructor() { super("Workspace"); this.Gravity = 196.2; } static props = ["Name", "Gravity"]; }, "Workspace");
registrar(class Players extends Servico {
  constructor() { super("Players"); this.LocalPlayer = null; this.PlayerAdded = new Sinal("PlayerAdded"); this.PlayerRemoving = new Sinal("PlayerRemoving"); }
  GetPlayers() { return this._filhos.filter((f) => f instanceof Player); }
}, "Players");
registrar(class ReplicatedStorage extends Servico { constructor() { super("ReplicatedStorage"); } }, "ReplicatedStorage");
registrar(class ServerScriptService extends Servico { constructor() { super("ServerScriptService"); } }, "ServerScriptService");
registrar(class StarterPlayer extends Servico { constructor() { super("StarterPlayer"); } }, "StarterPlayer");
registrar(class StarterPlayerScripts extends Servico { constructor() { super("StarterPlayerScripts"); } }, "StarterPlayerScripts");
registrar(class RunService extends Servico {
  constructor() { super("RunService"); this.Heartbeat = new Sinal("Heartbeat"); this.RenderStepped = new Sinal("RenderStepped"); }
  IsStudio() { return true; }
}, "RunService");

export class DataModel extends Instance {
  constructor() { super("Jogo"); }
  static naoCriavel = true;
  GetService(nome) {
    const s = this.FindFirstChild(nome) || this._filhos.find((f) => f.ClassName === nome);
    if (!s) throw new Error(`Serviço desconhecido: ${nome}`);
    return s;
  }
  get Workspace() { return this.GetService("Workspace"); }
  get Players() { return this.GetService("Players"); }
  get ReplicatedStorage() { return this.GetService("ReplicatedStorage"); }
  get ServerScriptService() { return this.GetService("ServerScriptService"); }
  get StarterPlayer() { return this.GetService("StarterPlayer"); }
  get RunService() { return this.GetService("RunService"); }
}
registrar(DataModel, "DataModel");

/** O "mundo": um DataModel com serviços, avisa render/editor de mudanças. */
export class Mundo {
  constructor() {
    this.ouvintes = { entrou: [], saiu: [], mudou: [] };
    this.assets = {};        // malhas importadas: id -> {obj, mtl, texturas}
    this.game = new DataModel();
    this.game._mundo = this;
    for (const s of ["Workspace", "Players", "ReplicatedStorage", "ServerScriptService", "StarterPlayer", "RunService"]) {
      const c = new CLASSES[s](); c._nome = s; c.Parent = this.game;
    }
    const sps = new CLASSES.StarterPlayerScripts(); sps.Parent = this.game.StarterPlayer;
  }
  get workspace() { return this.game.Workspace; }
  on(tipo, fn) { this.ouvintes[tipo].push(fn); }
  _entrar(i) { for (const f of this.ouvintes.entrou) f(i); }
  _sair(i) { for (const f of this.ouvintes.saiu) f(i); }
  _aoMudar(i, p) { for (const f of this.ouvintes.mudou) f(i, p); }
  partes() { return this.workspace.GetDescendants().filter((d) => d instanceof BasePart); }
  scripts() { return this.game.GetDescendants().filter((d) => d instanceof BaseScript); }
  contarPartes() { return this.partes().length; }
}

// --------------------------------------------------------------- salvamento
export const VERSAO_ARQUIVO = 1;

export function salvarInstancia(i) {
  const props = {};
  for (const p of i.constructor.props) {
    const v = i[p];
    props[p] = v && typeof v.toJSON === "function" ? v.toJSON() : v;
  }
  return { classe: i.ClassName, props, filhos: i._filhos.filter((f) => !f._temporaria).map(salvarInstancia) };
}

export function carregarInstancia(d, pai) {
  const i = new CLASSES[d.classe]();
  for (const [k, v] of Object.entries(d.props || {})) {
    if (k === "Name") i._nome = v;
    else if (["Position", "Size", "Rotation"].includes(k)) i[k] = Vector3.de(v);
    else if (k === "Color") i.Color = Color3.de(v);
    else i[k] = v;
  }
  for (const f of d.filhos || []) carregarInstancia(f, i);
  if (pai) i.Parent = pai;
  return i;
}

export function salvarMundo(m, nome = "Meu jogo") {
  const servicos = {};
  for (const s of m.game.GetChildren()) {
    if (s.ClassName === "Players" || s.ClassName === "RunService") continue;
    servicos[s.ClassName] = s.GetChildren().filter((f) => !f._temporaria).map(salvarInstancia);
  }
  return { formato: "rolox-studio", versao: VERSAO_ARQUIVO, nome, servicos, assets: m.assets };
}

export function carregarMundo(dados) {
  if (!dados || dados.formato !== "rolox-studio") throw new Error("Arquivo não é um projeto do Rolox Studio");
  const m = new Mundo();
  m.assets = dados.assets || {};
  for (const [servico, filhos] of Object.entries(dados.servicos || {})) {
    const s = m.game.FindFirstChild(servico) || m.game.GetChildren().find((c) => c.ClassName === servico);
    if (!s) continue;
    for (const f of filhos) {
      if (f.classe === "StarterPlayerScripts") {
        const alvo = s.FindFirstChildOfClass("StarterPlayerScripts");
        for (const ff of f.filhos || []) carregarInstancia(ff, alvo);
      } else carregarInstancia(f, s);
    }
  }
  return m;
}

/** Mundo inicial: chão e um ponto de nascimento. */
export function mundoInicial() {
  const m = new Mundo();
  const chao = criar("Part"); chao.Name = "Chao"; chao.Size = new Vector3(128, 1, 128);
  chao.Position = new Vector3(0, -0.5, 0); chao.Anchored = true; chao.Color = Color3.fromHex("#5b8c3a");
  chao.Parent = m.workspace;
  const sp = criar("SpawnLocation"); sp.Position = new Vector3(0, 0.5, 0); sp.Parent = m.workspace;
  return m;
}
