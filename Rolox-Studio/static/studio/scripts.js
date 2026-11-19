// Rolox Studio — execução de scripts.
//   LocalScript  -> Lua (Fengari) por padrão; roda no dispositivo do jogador.
//   Script       -> Python (Pyodide) por padrão; é o "server script".
//   ModuleScript -> Lua ou Python, quem decide é o dono do jogo.
// A linguagem vem da primeira linha:  _++linguagemprogroma++_ = lua   (ou python)

import { Color3, Instance, Sinal, Vector3, BaseScript, criar } from "./motor.js";

let contadorApi = 0;

// --------------------------------------------------------------------- Lua
const PRELUDIO_LUA = String.raw`
local js = require "js"
local api = js.global[__NOME_API]
local cacheInst = setmetatable({}, { __mode = "v" })
local InstMeta, V3Meta, C3Meta, SinalMeta = {}, {}, {}, {}
local wrap, unwrap

local function eh(v, f) return type(v) == "userdata" and api[f](api, v) end

wrap = function(v)
  if v == nil or v == js.null then return nil end
  if type(v) ~= "userdata" then return v end
  if api:ehV3(v) then return setmetatable({ X = v.X, Y = v.Y, Z = v.Z }, V3Meta) end
  if api:ehC3(v) then return setmetatable({ R = v.R, G = v.G, B = v.B }, C3Meta) end
  if api:ehInstancia(v) then
    local id = v.id
    local w = cacheInst[id]
    if w == nil then w = setmetatable({ __js = v }, InstMeta); cacheInst[id] = w end
    return w
  end
  if api:ehSinal(v) then return setmetatable({ __js = v }, SinalMeta) end
  if api:ehArray(v) then
    local t = {}
    for i = 0, v.length - 1 do t[i + 1] = wrap(v[i]) end
    return t
  end
  return v
end

unwrap = function(v)
  if type(v) == "table" then
    local m = getmetatable(v)
    if m == InstMeta or m == SinalMeta then return rawget(v, "__js") end
    if m == V3Meta then return api:v3(v.X, v.Y, v.Z) end
    if m == C3Meta then return api:c3(v.R, v.G, v.B) end
  end
  return v
end

local function unwrapTodos(...)
  local n = select("#", ...)
  local t = { ... }
  for i = 1, n do t[i] = unwrap(t[i]) end
  return table.unpack(t, 1, n)
end

InstMeta.__index = function(t, k)
  local o = rawget(t, "__js")
  local val = o[k]
  if type(val) == "userdata" and api:ehFuncao(val) then
    return function(_, ...) return wrap(val(o, unwrapTodos(...))) end
  end
  return wrap(val)
end
InstMeta.__newindex = function(t, k, v) rawget(t, "__js")[k] = unwrap(v) end
InstMeta.__tostring = function(t) return tostring(rawget(t, "__js").Name) end
InstMeta.__eq = function(a, b) return rawget(a, "__js") == rawget(b, "__js") end

-- tarefas (wait/spawn) com corrotinas
local tarefas = {}
local function retomar(co, ...)
  local ok, res = coroutine.resume(co, ...)
  if not ok then
    api:erro(tostring(res))
    return
  end
  if coroutine.status(co) ~= "dead" then
    tarefas[#tarefas + 1] = { co = co, acorda = api:agora() + (tonumber(res) or 0), inicio = api:agora() }
  end
end
function __spawn(fn, ...)
  local co = coroutine.create(fn)
  retomar(co, ...)
end
function __passo()
  local agora = api:agora()
  local prontas, resto = {}, {}
  for _, t in ipairs(tarefas) do
    if t.acorda <= agora then prontas[#prontas + 1] = t else resto[#resto + 1] = t end
  end
  tarefas = resto
  for _, t in ipairs(prontas) do retomar(t.co, agora - t.inicio) end
end

SinalMeta.__index = function(t, k)
  local s = rawget(t, "__js")
  if k == "Connect" or k == "connect" then
    return function(_, fn)
      return s:Connect(function(_this, ...)
        local a = table.pack(...)
        for i = 1, a.n do a[i] = wrap(a[i]) end
        __spawn(fn, table.unpack(a, 1, a.n))
      end)
    end
  end
  if k == "Wait" then
    return function(_)
      local recebido, valores = false, nil
      local c
      c = s:Connect(function(_this, ...)
        recebido = true; valores = table.pack(...); c:Disconnect()
      end)
      while not recebido do coroutine.yield(0) end
      for i = 1, valores.n do valores[i] = wrap(valores[i]) end
      return table.unpack(valores, 1, valores.n)
    end
  end
  return nil
end

function wait(s)
  s = tonumber(s) or 0.03
  return coroutine.yield(s)
end
task = {
  wait = wait,
  spawn = function(fn, ...) __spawn(fn, ...) end,
  delay = function(s, fn, ...) local a = table.pack(...); __spawn(function() wait(s); fn(table.unpack(a, 1, a.n)) end) end,
}
spawn, delay = task.spawn, task.delay

V3Meta.__index = function(v, k)
  if k == "Magnitude" then return math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z) end
  if k == "Unit" then local m = math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z); if m == 0 then m = 1 end; return Vector3.new(v.X / m, v.Y / m, v.Z / m) end
  if k == "x" then return v.X elseif k == "y" then return v.Y elseif k == "z" then return v.Z end
  return nil
end
V3Meta.__add = function(a, b) return Vector3.new(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V3Meta.__sub = function(a, b) return Vector3.new(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V3Meta.__mul = function(a, b)
  if type(a) == "number" then return Vector3.new(a * b.X, a * b.Y, a * b.Z) end
  if type(b) == "number" then return Vector3.new(a.X * b, a.Y * b, a.Z * b) end
  return Vector3.new(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V3Meta.__div = function(a, b) if type(b) == "number" then return Vector3.new(a.X / b, a.Y / b, a.Z / b) end return Vector3.new(a.X / b.X, a.Y / b.Y, a.Z / b.Z) end
V3Meta.__unm = function(a) return Vector3.new(-a.X, -a.Y, -a.Z) end
V3Meta.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
V3Meta.__tostring = function(v) return string.format("%g, %g, %g", v.X, v.Y, v.Z) end
C3Meta.__tostring = function(c) return string.format("%g, %g, %g", c.R, c.G, c.B) end

Vector3 = {
  new = function(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V3Meta) end,
}
Vector3.zero = Vector3.new(0, 0, 0)
Vector3.one = Vector3.new(1, 1, 1)
Color3 = {
  new = function(r, g, b) return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, C3Meta) end,
  fromRGB = function(r, g, b) return setmetatable({ R = (r or 0) / 255, G = (g or 0) / 255, B = (b or 0) / 255 }, C3Meta) end,
}
Instance = { new = function(classe, pai) return wrap(api:novaInstancia(classe, unwrap(pai))) end }

-- extras do Luau
function math.clamp(x, a, b) if x < a then return a elseif x > b then return b end return x end
function math.round(x) return math.floor(x + 0.5) end
function math.sign(x) if x > 0 then return 1 elseif x < 0 then return -1 end return 0 end
function string.split(s, sep)
  sep = sep or ","
  local t = {}
  for parte in (s .. sep):gmatch("(.-)" .. sep:gsub("%p", "%%%0")) do t[#t + 1] = parte end
  return t
end
table.find = function(t, v) for i, x in ipairs(t) do if x == v then return i end end return nil end

game = wrap(api.game)
workspace = game.Workspace
Workspace = workspace

-- números vindos do JS chegam como float (16.0); mostra 16
function __texto(v)
  if type(v) == "number" and math.tointeger(v) then return tostring(math.tointeger(v)) end
  return tostring(v)
end

local cacheModulos = {}
local function ambiente(jsScript, nome)
  local env = setmetatable({}, { __index = _G })
  env.script = wrap(jsScript)
  env.print = function(...)
    local t = {}
    for i = 1, select("#", ...) do t[#t + 1] = __texto((select(i, ...))) end
    api:imprimir(nome, table.concat(t, " "))
  end
  env.warn = function(...)
    local t = {}
    for i = 1, select("#", ...) do t[#t + 1] = __texto((select(i, ...))) end
    api:avisar(nome, table.concat(t, " "))
  end
  return env
end

function require(mod)
  local o = unwrap(mod)
  local info = api:fonteModulo(o)
  if info.erro ~= nil and info.erro ~= js.null then error(info.erro, 2) end
  local id = info.id
  if cacheModulos[id] ~= nil then return cacheModulos[id] end
  local chunk, err = load(info.codigo, "=" .. info.nome, "t", ambiente(o, info.nome))
  if not chunk then error(err, 2) end
  local r = chunk()
  cacheModulos[id] = r == nil and true or r
  return cacheModulos[id]
end

function __rodarScript(jsScript, codigo, nome)
  local chunk, err = load(codigo, "=" .. nome, "t", ambiente(jsScript, nome))
  if not chunk then api:erro(err); return end
  __spawn(chunk)
end
`;

export class ExecutorLua {
  constructor(api) {
    if (!window.fengari) throw new Error("Fengari (Lua) não carregou");
    const { lua, lauxlib, lualib, interop, to_luastring } = window.fengari;
    Object.assign(this, { lua, lauxlib, interop, to_luastring });
    this.nomeApi = `__roloxApi${++contadorApi}`;
    window[this.nomeApi] = api;
    const L = (this.L = lauxlib.luaL_newstate());
    lualib.luaL_openlibs(L);
    lauxlib.luaL_requiref(L, to_luastring("js"), interop.luaopen_js, 1);
    lua.lua_pop(L, 1);
    lua.lua_pushstring(L, to_luastring(this.nomeApi));
    lua.lua_setglobal(L, to_luastring("__NOME_API"));
    this._executar(PRELUDIO_LUA, "prelúdio");
  }
  _executar(codigo, nome) {
    const { lua, lauxlib, to_luastring, L } = this;
    if (lauxlib.luaL_loadbuffer(L, to_luastring(codigo), null, to_luastring("=" + nome)) !== lua.LUA_OK ||
        lua.lua_pcall(L, 0, 0, 0) !== lua.LUA_OK) {
      const msg = lua.lua_tojsstring(L, -1); lua.lua_pop(L, 1);
      throw new Error(msg);
    }
  }
  _chamarGlobal(nome, ...args) {
    const { lua, interop, to_luastring, L } = this;
    lua.lua_getglobal(L, to_luastring(nome));
    for (const a of args) interop.push(L, a);
    if (lua.lua_pcall(L, args.length, 0, 0) !== lua.LUA_OK) {
      const msg = lua.lua_tojsstring(L, -1); lua.lua_pop(L, 1);
      throw new Error(msg);
    }
  }
  rodar(script, codigo) { this._chamarGlobal("__rodarScript", script, codigo, script.Name); }
  passo() { this._chamarGlobal("__passo"); }
  fechar() { if (this.L) { this.lua.lua_close(this.L); this.L = null; } delete window[this.nomeApi]; }
}

// ------------------------------------------------------------------ Python
let pyodideCarregando = null;
export function carregarPython(saida) {
  if (pyodideCarregando) return pyodideCarregando;
  pyodideCarregando = (async () => {
    saida?.("Carregando Python (Pyodide, ~10 MB na primeira vez)...");
    let mod;
    try { mod = await import("/static/vendor/pyodide/pyodide.mjs"); }
    catch { mod = await import("https://cdn.jsdelivr.net/npm/pyodide@314.0.8/pyodide.mjs"); }
    const py = await mod.loadPyodide();
    saida?.("Python pronto.");
    return py;
  })();
  pyodideCarregando.catch(() => { pyodideCarregando = null; });
  return pyodideCarregando;
}

const BASE_PYTHON = `
import asyncio, types
from rolox import game, workspace, _Vector3, _Color3, _criar, _imprimir, _avisar, _agora, _fonte_modulo
Workspace = workspace

# No Pyodide, ".new" numa classe JS vira "new Classe(...)"; por isso estas versões em Python.
class Instance:
    @staticmethod
    def new(classe, pai=None):
        return _criar(classe, pai)

class Vector3:
    @staticmethod
    def new(x=0, y=0, z=0):
        return _Vector3.new(x, y, z)

Vector3.zero = Vector3.new(0, 0, 0)
Vector3.one = Vector3.new(1, 1, 1)

class Color3:
    @staticmethod
    def new(r=0, g=0, b=0):
        return _Color3.new(r, g, b)
    @staticmethod
    def fromRGB(r=0, g=0, b=0):
        return _Color3.fromRGB(r, g, b)

async def wait(s=0.03):
    t0 = _agora()
    await asyncio.sleep(float(s))
    return _agora() - t0

def _agendar(r):
    if asyncio.iscoroutine(r):
        asyncio.ensure_future(r)

class _Task:
    wait = staticmethod(wait)
    @staticmethod
    def spawn(fn, *a):
        _agendar(fn(*a))
    @staticmethod
    def delay(s, fn, *a):
        async def _d():
            await wait(s)
            _agendar(fn(*a))
        asyncio.ensure_future(_d())
task = _Task()

_modulos = {}
def _globais_base(nome, script):
    g = {k: v for k, v in globals().items() if not k.startswith("__")}
    def _print(*a, sep=" ", end="\\n"):
        _imprimir(nome, sep.join(str(x) for x in a))
    def _warn(*a):
        _avisar(nome, " ".join(str(x) for x in a))
    g.update(print=_print, warn=_warn, script=script, __name__=nome)
    return g

def require(m):
    info = _fonte_modulo(m)
    if info.erro:
        raise RuntimeError(info.erro)
    if info.id in _modulos:
        return _modulos[info.id]
    g = _globais_base(info.nome, m)
    exec(compile(info.codigo, info.nome, "exec"), g)
    ns = types.SimpleNamespace(**{k: v for k, v in g.items() if not k.startswith("_") and k not in _NOMES_BASE})
    _modulos[info.id] = ns
    return ns

_NOMES_BASE = set(globals()) | {"print", "warn", "script"}

def _parar_tudo():
    for t in asyncio.all_tasks():
        t.cancel()
    _modulos.clear()
`;

export class ExecutorPython {
  constructor(py, api) {
    this.py = py;
    this.api = api;
    py.registerJsModule("rolox", {
      game: api.game, workspace: api.game.Workspace, _Vector3: Vector3, _Color3: Color3,
      _criar: (classe, pai) => criar(String(classe), pai || undefined),
      _imprimir: (n, t) => api.imprimir(n, t), _avisar: (n, t) => api.avisar(n, t),
      _agora: () => api.agora(), _fonte_modulo: (m) => api.fonteModulo(m, "python"),
    });
    py.FS.writeFile("/home/pyodide/rolox_base.py", BASE_PYTHON);
    py.runPython("import sys, importlib\nsys.path.insert(0, '/home/pyodide')\nimport rolox_base\nimportlib.reload(rolox_base)");
    this.base = py.pyimport("rolox_base");
    globalThis.__roloxAgendarPy = (coro) => { try { this.base._agendar(coro); } finally { coro.destroy?.(); } };
  }
  async rodar(script, codigo) {
    const g = this.base._globais_base(script.Name, script);
    try { await this.py.runPythonAsync(codigo, { globals: g, filename: script.Name }); }
    catch (e) { this.api.erro(`${script.Name}: ${limparErroPython(e.message)}`); }
  }
  parar() { try { this.base._parar_tudo(); } catch { /* já parado */ } }
}

function limparErroPython(msg) {
  const linhas = String(msg).trim().split("\n");
  const i = linhas.findIndex((l) => l.includes('File "') && !l.includes("/lib/python") && !l.includes("_pyodide"));
  return (i >= 0 ? linhas.slice(i) : linhas.slice(-3)).join("\n");
}

// --------------------------------------------------------------- a API
export function criarApi(mundo, saida) {
  const api = {
    game: mundo.game,
    agora: () => performance.now() / 1000,
    v3: (x, y, z) => new Vector3(x, y, z),
    c3: (r, g, b) => new Color3(r, g, b),
    ehV3: (v) => v instanceof Vector3,
    ehC3: (v) => v instanceof Color3,
    ehInstancia: (v) => v instanceof Instance,
    ehSinal: (v) => v instanceof Sinal,
    ehArray: (v) => Array.isArray(v),
    ehFuncao: (v) => typeof v === "function",
    novaInstancia: (classe, pai) => criar(String(classe), pai || undefined),
    imprimir: (nome, texto) => saida(String(texto), "info", nome),
    avisar: (nome, texto) => saida(String(texto), "aviso", nome),
    erro: (texto) => saida(String(texto), "erro"),
    fonteModulo: (m, quem = "lua") => {
      if (!(m instanceof BaseScript) || m.ClassName !== "ModuleScript") return { erro: "require() precisa de um ModuleScript" };
      if (m.Linguagem !== quem) {
        return { erro: `O ModuleScript "${m.Name}" está em ${m.Linguagem}; um script em ${quem} só pode usar módulos em ${quem} (por enquanto).` };
      }
      return { id: m.id, nome: m.Name, codigo: m.CodigoExecutavel, erro: null };
    },
  };
  return api;
}
