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
    this._ancorada = false;
    this._colide = true;
    this._transp = 0;
    this._forma = "Block";
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
}
registrar(DataModel, "DataModel");

/** O "mundo": um DataModel com serviços, avisa render/editor de mudanças. */
export class Mundo {
  constructor() {
    this.ouvintes = { entrou: [], saiu: [], mudou: [] };
    this.assets = {};        // malhas importadas: id -> {obj, mtl, texturas}
    this.game = new DataModel();
    this.game._mundo = this;
    for (const s of ["Workspace", "Players", "ReplicatedStorage", "ServerScriptService", "StarterPlayer", "RunService", "Rede", "Cofre", "Tela", "Sons"]) {
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
    if (s.ClassName === "Players" || s.ClassName === "RunService" || ["Rede", "Cofre", "Tela", "Sons"].includes(s.ClassName)) continue;
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
