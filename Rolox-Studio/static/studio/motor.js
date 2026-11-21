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

// Materiais das peças (nomes do ROLOX). Alguns mudam a física do personagem:
//   Gelo escorrega, Areia deixa mais devagar, Borracha faz quicar.
export const MATERIAIS = ["Plastico", "Madeira", "Metal", "Grama", "Pedra", "Tijolo", "Concreto", "Areia",
  "Gelo", "Neon", "Vidro", "Tecido", "Borracha", "Lava", "Agua"];
const SEM_ACENTO = (t) => String(t ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
export function materialValido(v) {
  const k = SEM_ACENTO(v);
  return MATERIAIS.find((m) => m.toLowerCase() === k) || null;
}

export class BasePart extends Instance {
  constructor(nome) {
    super(nome);
    this._pos = new Vector3(0, 0.5, 0);
    this._tam = new Vector3(4, 1, 2);
    this._rot = new Vector3(0, 0, 0);
    this._cor = Color3.fromHex("#a3a2a5");
    this._ancorada = false;
    this._colide = true;
    this._transp = 0;
    this._forma = "Block";
    this._material = "Plastico";
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
  // estas também avisam quando mudam (o render e o mundo compartilhado precisam saber)
  get Anchored() { return this._ancorada; }
  set Anchored(v) { v = !!v; if (v === this._ancorada) return; this._ancorada = v; this._mudou("Anchored"); }
  get CanCollide() { return this._colide; }
  set CanCollide(v) { v = !!v; if (v === this._colide) return; this._colide = v; this._mudou("CanCollide"); }
  get Shape() { return this._forma; }
  set Shape(v) { v = ["Block", "Ball", "Cylinder"].includes(v) ? v : "Block"; if (v === this._forma) return; this._forma = v; this._mudou("Shape"); }
  get Material() { return this._material; }
  set Material(v) {
    const m = materialValido(v);
    if (!m) throw new Error(`Material desconhecido: ${v} (use ${MATERIAIS.join(", ")})`);
    if (m === this._material) return;
    this._material = m; this._mudou("Material");
  }
  Destroy() { this.Touched.limpar(); this.TouchEnded.limpar(); super.Destroy(); }
  static props = ["Name", "Position", "Size", "Rotation", "Color", "Material", "Anchored", "CanCollide", "Transparency", "Shape"];
}
registrar(class Part extends BasePart { constructor() { super("Part"); } }, "Part");

// ------------------------------------------------------ sons e vídeos do criador
// Arquivos enviados pelo criador no Studio do site (bucket "midias"). Midia = "<pasta>/<arquivo>".
//   workspace.Musica:Tocar() / :Parar()     (Som: Volume 0..1, Repetir, TocarAoComecar)
//   workspace.Telao:Tocar() / :Parar()      (TelaVideo: uma peça que passa o vídeo; ComSom, Repetir)
export const MIDIA = /^[0-9a-f-]{36}\/[0-9a-f]{16}\.(mp3|ogg|wav|webm|mp4)$/;
function definirMidia(i, v) { const s = String(v ?? ""); i._midia = s === "" || MIDIA.test(s) ? s : i._midia; i._mudou?.("Midia"); }
registrar(class Som extends Instance {
  constructor() {
    super("Som");
    this._midia = ""; this._volume = 1; this.Repetir = false; this.TocarAoComecar = false; this._tocando = false;
  }
  get Midia() { return this._midia; }
  set Midia(v) { definirMidia(this, v); }
  get Volume() { return this._volume; }
  set Volume(v) { this._volume = Math.max(0, Math.min(1, Number(v) || 0)); this._mudou("Volume"); }
  get Tocando() { return this._tocando; }
  Tocar() { this._tocando = true; this._mudou("Tocando"); }
  Parar() { this._tocando = false; this._mudou("Tocando"); }
  static props = ["Name", "Midia", "Volume", "Repetir", "TocarAoComecar"];
}, "Som");
registrar(class TelaVideo extends BasePart {
  constructor() {
    super("TelaVideo");
    this._ancorada = true; this._tam = new Vector3(8, 4.5, 0.3); this._cor = Color3.fromHex("#111111");
    this._midia = ""; this.Repetir = true; this.ComSom = false; this.TocarAoComecar = true; this._tocando = false;
  }
  get Midia() { return this._midia; }
  set Midia(v) { definirMidia(this, v); }
  get Tocando() { return this._tocando; }
  Tocar() { this._tocando = true; this._mudou("Tocando"); }
  Parar() { this._tocando = false; this._mudou("Tocando"); }
  static props = [...BasePart.props, "Midia", "Repetir", "ComSom", "TocarAoComecar"];
}, "TelaVideo");
registrar(class SpawnLocation extends BasePart {
  constructor() { super("SpawnLocation"); this.Anchored = true; this._tam = new Vector3(6, 1, 6); this._cor = Color3.fromHex("#4caf50"); }
}, "SpawnLocation");
// Checkpoint: encostou, passa a renascer aqui (sem script). Para obby e corrida.
registrar(class Checkpoint extends BasePart {
  constructor() {
    super("Checkpoint"); this.Anchored = true; this._tam = new Vector3(6, 1, 6);
    this._cor = Color3.fromHex("#ffb300"); this._material = "Neon";
  }
}, "Checkpoint");
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
registrar(class Workspace extends Servico {
  constructor() { super("Workspace"); this.Gravity = 196.2; }
  static props = ["Name", "Gravity"];
  /**
   * Raio: a primeira peça na linha que sai de `origem` na `direcao` (até `distancia`, padrão 500).
   * Devolve { Peca, Posicao, Distancia } ou nada. `ignorar`: uma peça ou Model para não contar (ex.: o próprio personagem).
   */
  Raio(origem, direcao, distancia = 500, ignorar = null) {
    const o = Vector3.de(origem), d0 = Vector3.de(direcao);
    if (!d0.Magnitude) return null;
    const d = d0.Unit, max = Math.min(2000, Math.max(0, +distancia || 500));
    let melhor = null;
    for (const p of this.GetDescendants()) {
      if (!(p instanceof BasePart) || p._visual || p.Transparency >= 1) continue;
      if (ignorar && (p === ignorar || p.EhDescendenteDe(ignorar))) continue;
      const t = raioCaixa(o, d, p);
      if (t !== null && t <= max && (!melhor || t < melhor.Distancia)) melhor = { Peca: p, Distancia: t };
    }
    if (!melhor) return null;
    melhor.Posicao = o.add(d.mul(melhor.Distancia));
    return melhor;
  }
}, "Workspace");

/** Distância até a caixa da peça (sem rotação; bola/cilindro contam como caixa). null = não acerta. */
function raioCaixa(o, d, p) {
  let tmin = 0, tmax = Infinity;
  for (const k of ["X", "Y", "Z"]) {
    const lo = p.Position[k] - p.Size[k] / 2, hi = p.Position[k] + p.Size[k] / 2;
    if (Math.abs(d[k]) < 1e-9) { if (o[k] < lo || o[k] > hi) return null; continue; }
    let t1 = (lo - o[k]) / d[k], t2 = (hi - o[k]) / d[k];
    if (t1 > t2) [t1, t2] = [t2, t1];
    tmin = Math.max(tmin, t1); tmax = Math.min(tmax, t2);
    if (tmin > tmax) return null;
  }
  return tmin;
}
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

// ------------------------------------------------------------------ Rede
// Mensagens entre os jogadores e o ANFITRIÃO (o jogador que roda os Scripts do jogo).
//   LocalScript: Rede:ParaServidor("abrirPorta", dados)         -> chega no anfitrião
//   Script:      Rede.Recebido:Connect(function(jogador, nome, dados) ... end)
//   Script:      Rede:ParaTodos("placar", dados) / Rede:ParaJogador(jogador, "oi", dados)
//   LocalScript: Rede.RecebidoDoServidor:Connect(function(nome, dados) ... end)
// dados: texto, número, verdadeiro/falso (ou nada). Jogando sozinho, tudo funciona igual (local).
export const REDE_NOME = /^[A-Za-z0-9_À-ÿ -]{1,40}$/;
export function dadosRede(v) {
  if (v === undefined || v === null) return null;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string") return v.slice(0, 500);
  throw new Error("Rede: os dados precisam ser texto, número ou verdadeiro/falso");
}
registrar(class Rede extends Servico {
  constructor() {
    super("Rede");
    this.Recebido = new Sinal("Recebido");                       // no anfitrião: (jogador, nome, dados)
    this.RecebidoDoServidor = new Sinal("RecebidoDoServidor");   // em todos: (nome, dados)
    this._enviar = null;                                         // posto pelo multijogador
  }
  _mandar(para, nome, dados) {
    nome = String(nome ?? "");
    if (!REDE_NOME.test(nome)) throw new Error("Rede: nome da mensagem inválido (use letras, números, _ ou -)");
    const d = dadosRede(dados);
    if (this._enviar) { this._enviar(para, nome, d); return; }
    // sozinho (Studio ou jogo sem multijogador): entrega aqui mesmo, no próximo quadro
    const eu = this._pai?.FindFirstChild?.("Players")?.LocalPlayer;
    setTimeout(() => {
      if (para === "servidor") this.Recebido.Fire(eu, nome, d);
      else this.RecebidoDoServidor.Fire(nome, d);
    }, 0);
  }
  ParaServidor(nome, dados) { this._mandar("servidor", nome, dados); }
  ParaTodos(nome, dados) { this._mandar("todos", nome, dados); }
  ParaJogador(jogador, nome, dados) {
    this._mandar(jogador?._redeId ? String(jogador._redeId) : "eu", nome, dados);
  }
}, "Rede");

// ----------------------------------------------------------------- Cofre
// Dados do PRÓPRIO jogador que ficam salvos neste jogo (voltam na próxima vez que ele jogar).
//   local moedas = game:GetService("Cofre"):Ler("moedas", 0)
//   game:GetService("Cofre"):Salvar("moedas", moedas + 1)
//   game:GetService("Cofre"):Somar("vitorias", 1)       -- soma e devolve o novo valor
// Chaves: letras, números e _ (até 40). Valores: texto (até 1000), número ou verdadeiro/falso.
// Salva sozinho a cada 3 s e ao sair. No Studio e no modo teste fica só na memória.
export const COFRE_CHAVE = /^[A-Za-z0-9_]{1,40}$/;
registrar(class Cofre extends Servico {
  constructor() {
    super("Cofre");
    this._dados = {};
    this._sujos = new Set();
    this.Salvo = new Sinal("Salvo");
  }
  _chave(chave) {
    const k = String(chave ?? "");
    if (!COFRE_CHAVE.test(k)) throw new Error("Cofre: chave inválida (use letras, números ou _, até 40)");
    return k;
  }
  Ler(chave, padrao) {
    const k = this._chave(chave);
    return k in this._dados ? this._dados[k] : (padrao === undefined ? null : padrao);
  }
  Salvar(chave, valor) {
    const k = this._chave(chave);
    if (valor === undefined || valor === null) delete this._dados[k];
    else {
      if (typeof valor === "string") valor = valor.slice(0, 1000);
      else if (typeof valor === "number") { if (!Number.isFinite(valor)) throw new Error("Cofre: número inválido"); }
      else if (typeof valor !== "boolean") throw new Error("Cofre: guarde texto, número ou verdadeiro/falso");
      if (!(k in this._dados) && Object.keys(this._dados).length >= 50) throw new Error("Cofre: até 50 chaves por jogo");
      this._dados[k] = valor;
    }
    this._sujos.add(k);
    return valor ?? null;
  }
  Somar(chave, n = 1) {
    const atual = Number(this.Ler(chave, 0)) || 0;
    return this.Salvar(chave, atual + (Number(n) || 0));
  }
  Apagar(chave) { this.Salvar(chave, null); }
  _carregar(obj) { if (obj && typeof obj === "object") this._dados = { ...obj }; this._sujos.clear(); }
  _pendentes() {
    if (!this._sujos.size) return null;
    const r = {};
    for (const k of this._sujos) r[k] = k in this._dados ? this._dados[k] : null;
    this._sujos.clear();
    return r;
  }
}, "Cofre");

// ----------------------------------------------------------- Tela e Sons
// O que aparece por cima do jogo e os sons — de CADA jogador (para todos verem, use a Rede).
//   Tela:Texto("placar", "Moedas: 3", "topo")      lugares: topo, centro, baixo, esquerda, direita
//   Tela:Botao("abrir", "Abrir a porta", "baixo")   +  Tela.Clicado:Connect(function(id) ... end)
//   Tela:Barra("vida", 80, 100, "topo")             Tela:Aviso("Você venceu!", 3)
//   Tela:Remover("placar") / Tela:Limpar()
//   Sons:Tocar("moeda")   (moeda, pulo, vitoria, dano, clique, porta, explosao, erro)
//   Sons:Musica("calma")  (calma, acao; "" para parar) — sons gerados na hora, sem arquivos
export const TELA_LUGARES = ["topo", "centro", "baixo", "esquerda", "direita"];
export const SONS = ["moeda", "pulo", "vitoria", "dano", "clique", "porta", "explosao", "erro"];
export const MUSICAS = ["calma", "acao"];
const TELA_ID = /^[A-Za-z0-9_-]{1,30}$/;
registrar(class Tela extends Servico {
  constructor() {
    super("Tela");
    this._itens = new Map();                 // id -> {tipo, texto, lugar, valor, maximo}
    this.Clicado = new Sinal("Clicado");
    this.Respondeu = new Sinal("Respondeu"); // (id, opção escolhida, número da opção 1..4)
    this.Mudou = new Sinal("Mudou");         // para quem desenha (página do jogo)
  }
  _id(id) { const k = String(id ?? ""); if (!TELA_ID.test(k)) throw new Error("Tela: id inválido (letras, números, _ ou -)"); return k; }
  _lugar(l) { return TELA_LUGARES.includes(l) ? l : "topo"; }
  _por(id, item) {
    if (!this._itens.has(id) && this._itens.size >= 40) throw new Error("Tela: no máximo 40 itens");
    this._itens.set(id, item); this.Mudou.Fire(id, item);
  }
  Texto(id, texto, lugar) { const k = this._id(id); this._por(k, { tipo: "texto", texto: String(texto ?? "").slice(0, 200), lugar: this._lugar(lugar) }); }
  Botao(id, texto, lugar) { const k = this._id(id); this._por(k, { tipo: "botao", texto: String(texto ?? "").slice(0, 40), lugar: this._lugar(lugar ?? "baixo") }); }
  Barra(id, valor, maximo, lugar) {
    const k = this._id(id), max = Math.max(1, Number(maximo) || 100);
    this._por(k, { tipo: "barra", valor: Math.max(0, Math.min(max, Number(valor) || 0)), maximo: max, lugar: this._lugar(lugar) });
  }
  Aviso(texto, segundos) {
    const id = `_aviso${Date.now()}${Math.floor(Math.random() * 1000)}`;
    this._itens.set(id, { tipo: "aviso", texto: String(texto ?? "").slice(0, 200), lugar: "centro" });
    this.Mudou.Fire(id, this._itens.get(id));
    setTimeout(() => this.Remover(id), Math.max(0.5, Math.min(30, Number(segundos) || 3)) * 1000);
  }
  Remover(id) { const k = String(id ?? ""); if (this._itens.delete(k)) this.Mudou.Fire(k, null); }
  Limpar() { for (const k of [...this._itens.keys()]) this.Remover(k); }
  _clicar(id) { if (this._itens.get(id)?.tipo === "botao") this.Clicado.Fire(id); }
  /** 💬 Pergunta com até 4 botões: tela:Pergunta("loja", "Quer a espada?", "Sim", "Não").
   *  A escolha chega em tela.Respondeu(id, opção, número) e a caixa some. */
  Pergunta(id, texto, ...opcoes) {
    const k = this._id(id);
    const lista = opcoes.flat().map((o) => String(o ?? "").slice(0, 30)).filter(Boolean).slice(0, 4);
    if (!lista.length) lista.push("OK");
    this._por(k, { tipo: "pergunta", texto: String(texto ?? "").slice(0, 200), opcoes: lista, lugar: "centro" });
  }
  _responder(id, n) {
    const item = this._itens.get(id);
    if (item?.tipo !== "pergunta" || !(n >= 0 && n < item.opcoes.length)) return;
    this.Remover(id);
    this.Respondeu.Fire(id, item.opcoes[n], n + 1);
  }
}, "Tela");
registrar(class Sons extends Servico {
  constructor() { super("Sons"); this.Tocou = new Sinal("Tocou"); this.musica = ""; }
  Tocar(nome) {
    const n = String(nome ?? "");
    if (!SONS.includes(n)) throw new Error(`Sons: use ${SONS.join(", ")}`);
    this.Tocou.Fire("som", n);
  }
  Musica(nome) {
    const n = String(nome ?? "");
    if (n && !MUSICAS.includes(n)) throw new Error(`Sons: músicas ${MUSICAS.join(", ")} (ou "" para parar)`);
    this.musica = n; this.Tocou.Fire("musica", n);
  }
}, "Sons");

// -------------------------------------------------------------- Emblemas
// Conquistas do jogo, dadas pelos scripts. Ficam para sempre na página do jogador.
//   game:GetService("Emblemas"):Dar("zerou", "Zerou o Obby", "🏆")   -- uma vez só por jogador
//   if Emblemas:Tem("zerou") then ... end
export const EMBLEMA_CODIGO = /^[A-Za-z0-9_]{1,30}$/;
registrar(class Emblemas extends Servico {
  constructor() {
    super("Emblemas");
    this._tem = new Set();
    this.Ganhou = new Sinal("Ganhou");        // (codigo, nome, emoji) — só na 1ª vez
  }
  Dar(codigo, nome, emoji) {
    const c = String(codigo ?? "");
    if (!EMBLEMA_CODIGO.test(c)) throw new Error("Emblemas: código inválido (letras, números ou _, até 30)");
    if (this._tem.has(c)) return false;
    if (this._tem.size >= 30) throw new Error("Emblemas: até 30 por jogo");
    this._tem.add(c);
    this.Ganhou.Fire(c, String(nome ?? c).slice(0, 40), String(emoji ?? "🏅").slice(0, 8) || "🏅");
    return true;
  }
  Tem(codigo) { return this._tem.has(String(codigo ?? "")); }
  _carregar(lista) { this._tem = new Set(Array.isArray(lista) ? lista.map(String) : []); }
}, "Emblemas");

// --------------------------------------------------------------- Animar
// Animações suaves de peças, sem escrever laço:
//   local anim = game:GetService("Animar")
//   anim:Mover(peca, Vector3.new(0, 10, 0), 2)          -- vai até a posição em 2 s
//   anim:Mover(peca, Vector3.new(0, 10, 0), 2, "suave") -- estilos: linear, suave, quicar, elastico
//   anim:Girar(peca, Vector3.new(0, 180, 0), 1) · anim:Cor(peca, Color3.fromRGB(255,0,0), 1)
//   anim:Tamanho(peca, Vector3.new(8, 1, 8), 1) · anim:Sumir(peca, 1) · anim:Aparecer(peca, 1)
//   anim:VaiEVolta(peca, Vector3.new(0, 5, 0), 2)      -- anda até pos+deslocamento e volta, para sempre
//   anim:Parar(peca) · anim.Terminou:Connect(function(peca, tipo) ... end)
export const ESTILOS = {
  linear: (t) => t,
  suave: (t) => t * t * (3 - 2 * t),
  quicar: (t) => {
    const n = 7.5625, d = 2.75;
    if (t < 1 / d) return n * t * t;
    if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75;
    if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375;
    return n * (t -= 2.625 / d) * t + 0.984375;
  },
  elastico: (t) => (t === 0 || t === 1 ? t : 2 ** (-10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1),
};
const misturar = (a, b, t) => a + (b - a) * t;
registrar(class Animar extends Servico {
  constructor() { super("Animar"); this._lista = []; this.Terminou = new Sinal("Terminou"); }
  _nova(peca, tipo, prop, de, para, s, estilo, extra = {}) {
    if (!(peca instanceof BasePart)) throw new Error("Animar: o 1º valor precisa ser uma peça");
    const f = ESTILOS[String(estilo ?? "suave")] ;
    if (!f) throw new Error(`Animar: estilos ${Object.keys(ESTILOS).join(", ")}`);
    this._lista = this._lista.filter((a) => !(a.peca === peca && a.prop === prop));    // a nova substitui
    if (this._lista.length >= 300) throw new Error("Animar: animações demais ao mesmo tempo");
    this._lista.push({ peca, tipo, prop, de, para, dur: Math.max(0.01, +s || 1), t: 0, f, ...extra });
    return true;
  }
  Mover(peca, destino, s, estilo) { return this._nova(peca, "Mover", "Position", peca.Position, Vector3.de(destino), s, estilo); }
  Girar(peca, rotacao, s, estilo) { return this._nova(peca, "Girar", "Rotation", peca.Rotation, Vector3.de(rotacao), s, estilo); }
  Tamanho(peca, tam, s, estilo) { return this._nova(peca, "Tamanho", "Size", peca.Size, Vector3.de(tam), s, estilo); }
  Cor(peca, cor, s, estilo) { return this._nova(peca, "Cor", "Color", peca.Color, Color3.de(cor), s, estilo); }
  Sumir(peca, s, estilo) { return this._nova(peca, "Sumir", "Transparency", peca.Transparency, 1, s, estilo, { colideNoFim: false }); }
  Aparecer(peca, s, estilo) {
    peca.CanCollide = true;
    return this._nova(peca, "Aparecer", "Transparency", peca.Transparency, 0, s, estilo);
  }
  VaiEVolta(peca, deslocamento, s, estilo) {
    return this._nova(peca, "VaiEVolta", "Position", peca.Position, peca.Position.add(Vector3.de(deslocamento)), s, estilo, { repetir: true });
  }
  Parar(peca) { this._lista = this._lista.filter((a) => a.peca !== peca); }
  Animando(peca) { return this._lista.some((a) => a.peca === peca); }
  _passo(dt) {
    if (!this._lista.length) return;
    const fim = [];
    for (const a of this._lista) {
      if (a.peca._destruida) { a.morta = true; continue; }
      a.t += dt;
      let k = Math.min(1, a.t / a.dur);
      if (a.repetir) { const ciclo = (a.t / a.dur) % 2; k = ciclo <= 1 ? ciclo : 2 - ciclo; }
      const e = a.f(k);
      if (a.prop === "Color") a.peca.Color = new Color3(misturar(a.de.R, a.para.R, e), misturar(a.de.G, a.para.G, e), misturar(a.de.B, a.para.B, e));
      else if (a.prop === "Transparency") a.peca.Transparency = misturar(a.de, a.para, e);
      else a.peca[a.prop] = new Vector3(misturar(a.de.X, a.para.X, e), misturar(a.de.Y, a.para.Y, e), misturar(a.de.Z, a.para.Z, e));
      if (!a.repetir && a.t >= a.dur) { a.morta = true; fim.push(a); }
    }
    this._lista = this._lista.filter((a) => !a.morta);
    for (const a of fim) {
      if (a.colideNoFim === false) a.peca.CanCollide = false;
      this.Terminou.Fire(a.peca, a.tipo);
    }
  }
}, "Animar");

// ----------------------------------------------------------------- Ceu
// Céu e luz do jogo (cada jogador vê o seu: use no LocalScript, ou ajuste no Studio).
//   local ceu = game:GetService("Ceu")
//   ceu.Hora = 18          -- 0 a 24 (6 = amanhecer, 12 = meio-dia, 18 = pôr do sol, 0 = noite)
//   ceu.Neblina = 0.5      -- 0 (nenhuma) a 1 (muita)
//   ceu.Estrelas = true    -- estrelas aparecem à noite
registrar(class Ceu extends Servico {
  constructor() { super("Ceu"); this._hora = 12; this._neblina = 0; this._estrelas = true; }
  get Hora() { return this._hora; }
  set Hora(v) { const n = Number(v); this._hora = Number.isFinite(n) ? ((n % 24) + 24) % 24 : 12; this._mudou("Hora"); }
  get Neblina() { return this._neblina; }
  set Neblina(v) { this._neblina = Math.max(0, Math.min(1, +v || 0)); this._mudou("Neblina"); }
  get Estrelas() { return this._estrelas; }
  set Estrelas(v) { this._estrelas = !!v; this._mudou("Estrelas"); }
  static props = ["Hora", "Neblina", "Estrelas"];
}, "Ceu");

// -------------------------------------------------------------- Efeitos
// Efeitos especiais (o jogo desenha; os scripts só pedem):
//   local fx = game:GetService("Efeitos")
//   fx:Explosao(posicao, raio)   -- clarão + som + empurra peças soltas + dano em quem está perto (até 100 no centro)
//   fx:Confete(posicao)          -- festa de cores (vitória!)
//   fx:Brilho(peca, segundos)    -- a peça pisca brilhando
//   fx:Fumaca(posicao)
registrar(class Efeitos extends Servico {
  constructor() { super("Efeitos"); this.Mostrar = new Sinal("Mostrar"); this.Explodiu = new Sinal("Explodiu"); }
  Explosao(posicao, raio = 10, dano = true) {
    const c = Vector3.de(posicao), r = Math.max(1, Math.min(60, +raio || 10));
    this.Mostrar.Fire("explosao", c, r);
    try { this._pai?.GetService?.("Sons")?.Tocar("explosao"); } catch { /* sem som */ }
    const ws = this._pai?.GetService?.("Workspace");
    const atingidos = [];
    for (const p of ws ? ws.GetDescendants() : []) {
      if (!(p instanceof BasePart) || p._visual) continue;
      const dif = p.Position.sub(c), dist = dif.Magnitude;
      if (dist > r) continue;
      const forca = 1 - dist / r;
      const hum = p.Name === "HumanoidRootPart" ? p.Parent?.FindFirstChildOfClass("Humanoid") : null;
      if (hum && dano) { hum.TakeDamage(Math.round(100 * forca)); atingidos.push(p.Parent); }
      if (!p.Anchored) {
        const dir = dist > 0.01 ? dif.Unit : new Vector3(0, 1, 0);
        p.Velocity = p.Velocity.add(dir.mul(120 * forca)).add(new Vector3(0, 60 * forca, 0));
        if (hum) p._empurrao = dir.mul(80 * forca);
      }
    }
    this.Explodiu.Fire(c, r);
    return atingidos.length;
  }
  Confete(posicao) { this.Mostrar.Fire("confete", Vector3.de(posicao), 6); }
  Fumaca(posicao) { this.Mostrar.Fire("fumaca", Vector3.de(posicao), 4); }
  Brilho(peca, segundos = 1) {
    if (!(peca instanceof BasePart)) throw new Error("Efeitos: Brilho precisa de uma peça");
    this.Mostrar.Fire("brilho", peca, Math.max(0.1, Math.min(10, +segundos || 1)));
  }
}, "Efeitos");

// -------------------------------------------------------------- Internet
// Pesquisa segura feita pelo servidor do ROLOX (Wikipédia e DuckDuckGo com busca segura).
//   local net = game:GetService("Internet")
//   net.Resultado:Connect(function(termo, texto) print(texto) end)
//   net:Pesquisar("dinossauros")      -- a resposta chega no Resultado (não trava o jogo)
registrar(class Internet extends Servico {
  constructor() {
    super("Internet");
    this.Resultado = new Sinal("Resultado");       // (termo, texto, lista)
    this._buscar = null;                           // posto pela página (site); sem ele: sem internet
  }
  Pesquisar(termo) {
    const t = String(termo ?? "").trim().slice(0, 100);
    if (t.length < 2) throw new Error("Internet: pesquise pelo menos 2 letras");
    if (!this._buscar) { setTimeout(() => this.Resultado.Fire(t, "Sem internet aqui (abra pelo site do ROLOX).", []), 0); return; }
    this._buscar(t).then(
      (d) => this.Resultado.Fire(t, String(d.texto ?? ""), Array.isArray(d.resultados) ? d.resultados.map((r) => `${r.titulo}: ${r.resumo}`) : []),
      (e) => this.Resultado.Fire(t, `Erro na pesquisa: ${e.message}`, []));
  }
}, "Internet");

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
  get Rede() { return this.GetService("Rede"); }
  get Cofre() { return this.GetService("Cofre"); }
  get Tela() { return this.GetService("Tela"); }
  get Sons() { return this.GetService("Sons"); }
  get Emblemas() { return this.GetService("Emblemas"); }
  get Internet() { return this.GetService("Internet"); }
  get Animar() { return this.GetService("Animar"); }
  get Ceu() { return this.GetService("Ceu"); }
  get Efeitos() { return this.GetService("Efeitos"); }
}
registrar(DataModel, "DataModel");

/** O "mundo": um DataModel com serviços, avisa render/editor de mudanças. */
export class Mundo {
  constructor() {
    this.ouvintes = { entrou: [], saiu: [], mudou: [] };
    this.assets = {};        // malhas importadas: id -> {obj, mtl, texturas}
    this.game = new DataModel();
    this.game._mundo = this;
    for (const s of ["Workspace", "Players", "ReplicatedStorage", "ServerScriptService", "StarterPlayer", "RunService", "Rede", "Cofre", "Tela", "Sons", "Emblemas", "Internet", "Animar", "Ceu", "Efeitos"]) {
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
    else if (k === "Material") { if (materialValido(v)) i.Material = v; }
    else i[k] = v;
  }
  for (const f of d.filhos || []) carregarInstancia(f, i);
  if (pai) i.Parent = pai;
  return i;
}

export function salvarMundo(m, nome = "Meu jogo") {
  const servicos = {};
  for (const s of m.game.GetChildren()) {
    if (s.ClassName === "Players" || s.ClassName === "RunService" || ["Rede", "Cofre", "Tela", "Sons", "Emblemas", "Internet", "Animar", "Ceu", "Efeitos"].includes(s.ClassName)) continue;
    servicos[s.ClassName] = s.GetChildren().filter((f) => !f._temporaria).map(salvarInstancia);
  }
  const c = m.game.Ceu;
  return { formato: "rolox-studio", versao: VERSAO_ARQUIVO, nome, servicos, assets: m.assets,
           ceu: { Hora: c.Hora, Neblina: c.Neblina, Estrelas: c.Estrelas } };
}

export function carregarMundo(dados) {
  if (!dados || dados.formato !== "rolox-studio") throw new Error("Arquivo não é um projeto do Rolox Studio");
  const m = new Mundo();
  m.assets = dados.assets || {};
  if (dados.ceu && typeof dados.ceu === "object") {
    for (const k of ["Hora", "Neblina", "Estrelas"]) if (k in dados.ceu) m.game.Ceu[k] = dados.ceu[k];
  }
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
