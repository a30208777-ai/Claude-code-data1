// Rolox Studio — editor (interface). Modo "leve" (celular) e "pesado" (PC).

import { OrbitControls } from "three/addons/OrbitControls.js";
import { TransformControls } from "three/addons/TransformControls.js";
import {
  BasePart, BaseScript, Color3, Vector3, criar, mundoInicial, salvarMundo, carregarMundo, definirReporteDeErro,
} from "./motor.js";
import { Render } from "./render.js";
import { Jogo } from "./jogo.js";
import { importarNoMundo } from "./importar_obj.js";
import { PCtoCelular, ehCelular, LIMITES } from "./pctocelular.js";
import { carregarPython } from "./scripts.js";

const MODO = document.body.dataset.modo;           // "leve" | "pesado"
const PESADO = MODO === "pesado";
const LIMITE_PARTES = PESADO ? 5000 : 400;
const CELULAR = ehCelular();
const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...filhos) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f != null) e.append(f.nodeType ? f : document.createTextNode(String(f)));
  return e;
};

const AVISO_PYTHON_LOCAL =
  "Ei!!! Se você mudar para Python, o seu jogo pode perder jogadores (retenção), " +
  "porque o usuário precisa rodar Python no celular dele pelo Termux.";
const LINK_PYTHON = "/aprender/python-no-celular";

const estado = { mundo: null, sel: null, jogo: null, nome: null, sujo: false };

// --------------------------------------------------------------- saída
function saida(texto, tipo = "info", origem) {
  const caixa = $("#saida");
  const linha = el("div", { class: tipo });
  const hora = new Date().toLocaleTimeString("pt-BR", { hour12: false });
  linha.append(`${hora}  `);
  if (origem) linha.append(el("span", { class: "origem" }, `[${origem}] `));
  linha.append(String(texto));
  caixa.append(linha);
  while (caixa.childElementCount > 400) caixa.firstChild.remove();
  caixa.scrollTop = caixa.scrollHeight;
  if (tipo === "erro" && !PESADO) marcarAba("painelSaida");
}
definirReporteDeErro((e) => saida(e?.message || String(e), "erro"));

// ------------------------------------------------------------------ modal
function modal(conteudo, botoes = [{ texto: "OK", valor: true, destaque: true }]) {
  return new Promise((ok) => {
    const m = $("#modal"), t = $("#modalTexto"), b = $("#modalBotoes");
    t.replaceChildren(...[].concat(conteudo).map((c) => (typeof c === "string" ? el("p", {}, c) : c)));
    b.replaceChildren(...botoes.map((x) => el("button", {
      class: x.destaque ? "destaque" : "", onclick: () => { m.hidden = true; ok(x.valor); },
    }, x.texto)));
    m.hidden = false;
    (t.querySelector("input") || b.lastChild)?.focus();
  });
}
async function perguntar(texto, padrao = "") {
  const campo = el("input", { type: "text", value: padrao });
  campo.addEventListener("keydown", (e) => { if (e.key === "Enter") $("#modalBotoes").lastChild.click(); });
  const ok = await modal([texto, campo], [{ texto: "Cancelar", valor: false }, { texto: "OK", valor: true, destaque: true }]);
  return ok ? campo.value.trim() : null;
}

// ------------------------------------------------------------------- cena
const canvas = $("#viewport");
const render = new Render(canvas, mundoInicial(), MODO);
estado.mundo = render.mundo;
const orbita = new OrbitControls(render.camera, canvas);
orbita.enableDamping = true;
orbita.target.set(0, 0, 0);
let gizmo = null;
if (PESADO) {
  gizmo = new TransformControls(render.camera, canvas);
  gizmo.setTranslationSnap(0.5);
  gizmo.setScaleSnap(0.5);
  gizmo.addEventListener("dragging-changed", (e) => { orbita.enabled = !e.value; });
  gizmo.addEventListener("objectChange", () => {
    const i = estado.sel, o = gizmo.object;
    if (!i || !o) return;
    i.Position = new Vector3(o.position.x, o.position.y, o.position.z);
    if (gizmo.getMode() === "scale" && o.isMesh) i.Size = new Vector3(o.scale.x, o.scale.y, o.scale.z);
    else if (gizmo.getMode() === "scale" && o.children[0]?.userData.tamanho) {
      const t = o.children[0].userData.tamanho;
      i.Size = new Vector3(o.scale.x * t.x, o.scale.y * t.y, o.scale.z * t.z);
    }
    estado.sujo = true;
    desenharProps();
  });
  render.cena.add(gizmo.getHelper ? gizmo.getHelper() : gizmo);
}

// clique/toque na cena seleciona
let inicioToque = null;
canvas.addEventListener("pointerdown", (e) => { inicioToque = [e.clientX, e.clientY]; });
canvas.addEventListener("pointerup", (e) => {
  if (estado.jogo || !inicioToque) return;
  const movimento = Math.hypot(e.clientX - inicioToque[0], e.clientY - inicioToque[1]);
  inicioToque = null;
  if (movimento > 6 || gizmo?.dragging) return;
  const r = canvas.getBoundingClientRect();
  const alvo = render.pegar(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  selecionar(alvo && !alvo._temporaria ? alvo : null);
});

function loop() {
  if (estado.jogo) estado.jogo.passo();
  else orbita.update();
  $("#infoCena").textContent = estado.jogo
    ? `Jogando · ${CELULAR || "ontouchstart" in window ? "joystick + botão de pular" : "WASD/setas + espaço"}`
    : `${estado.mundo.contarPartes()} peças · limite ${LIMITE_PARTES}${estado.nome ? " · " + estado.nome : ""}${estado.sujo ? " ●" : ""}`;
  render.desenhar();
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

// ---------------------------------------------------------------- explorer
const ICONES = {
  Workspace: "🌍", Part: "▫️", SpawnLocation: "🟩", MeshPart: "🧊", Model: "📦", Folder: "📁",
  Script: "🐍", LocalScript: "📜", ModuleScript: "🧩", ServerScriptService: "🖥️", ReplicatedStorage: "🗄️",
  StarterPlayer: "🧍", StarterPlayerScripts: "📂",
};
const SERVICOS_VISIVEIS = ["Workspace", "ServerScriptService", "ReplicatedStorage", "StarterPlayer"];

function desenharExplorer() {
  const raiz = $("#explorer");
  const no = (i) => {
    const filhos = i.GetChildren().filter((f) => !f._temporaria);
    const linha = el("div", {
      class: `no${estado.sel === i ? " selecionado" : ""}`, role: "treeitem", "aria-selected": estado.sel === i ? "true" : "false",
      onclick: (e) => { e.stopPropagation(); selecionar(i); },
      ondblclick: () => { if (i instanceof BaseScript) abrirScript(i); },
    }, el("span", { class: "icone" }, ICONES[i.ClassName] || "•"), i.Name,
      i instanceof BaseScript ? el("span", { class: "classe" }, i.Linguagem) : el("span", { class: "classe" }, i.ClassName));
    const li = el("li", {}, linha);
    if (filhos.length) li.append(el("ul", { role: "group" }, filhos.map(no)));
    return li;
  };
  raiz.replaceChildren(...SERVICOS_VISIVEIS.map((s) => no(estado.mundo.game.FindFirstChild(s))));
}

function selecionar(i) {
  estado.sel = i;
  if (gizmo) {
    const o = i instanceof BasePart ? render.objetoDe(i) : null;
    if (o && !estado.jogo) gizmo.attach(o); else gizmo.detach();
  }
  desenharExplorer();
  desenharProps();
}

// ----------------------------------------------------------- propriedades
function desenharProps() {
  const caixa = $("#props");
  const i = estado.sel;
  if (!i || i._destruida) { caixa.replaceChildren(el("p", { class: "vazio" }, "Selecione algo no Explorer ou na cena.")); return; }
  const linhas = [el("p", { class: "vazio" }, `${i.ClassName}`)];
  const linha = (rotulo, campo) => el("div", { class: "prop" }, el("label", {}, rotulo), campo);
  const marcar = () => { estado.sujo = true; desenharExplorer(); };
  const ehServico = i.constructor.naoCriavel;

  if (!ehServico) {
    linhas.push(linha("Name", el("input", { type: "text", value: i.Name, maxlength: 60,
      onchange: (e) => { i.Name = e.target.value || i.ClassName; marcar(); } })));
  }
  const vec = (prop) => {
    const v = i[prop];
    const campos = ["X", "Y", "Z"].map((k) => el("input", { type: "number", step: "0.5", value: +v[k].toFixed(3), "aria-label": `${prop} ${k}`,
      onchange: () => { i[prop] = new Vector3(...campos.map((c) => +c.value)); marcar(); sincronizarGizmo(); } }));
    return linha(prop, el("div", { class: "vec" }, campos));
  };
  for (const p of i.constructor.props) {
    if (p === "Name" || p === "Source") continue;
    const v = i[p];
    if (v instanceof Vector3) linhas.push(vec(p));
    else if (v instanceof Color3) linhas.push(linha(p, el("input", { type: "color", value: v.toHex(), oninput: (e) => { i.Color = e.target.value; marcar(); } })));
    else if (typeof v === "boolean") linhas.push(linha(p, el("input", { type: "checkbox", checked: v, onchange: (e) => { i[p] = e.target.checked; marcar(); } })));
    else if (p === "Shape") {
      linhas.push(linha(p, el("select", { onchange: (e) => { i.Shape = e.target.value; i._mudou("Shape"); marcar(); } },
        ["Block", "Ball", "Cylinder"].map((s) => el("option", { value: s, selected: s === v }, { Block: "Bloco", Ball: "Bola", Cylinder: "Cilindro" }[s])))));
    } else if (typeof v === "number") {
      linhas.push(linha(p, el("input", { type: "number", step: p === "Transparency" ? "0.1" : "1", value: v,
        onchange: (e) => { i[p] = +e.target.value; marcar(); } })));
    } else if (p === "MeshId") linhas.push(linha(p, el("input", { type: "text", value: v, readonly: true })));
  }
  if (i instanceof BaseScript) {
    const sel = el("select", { onchange: (e) => mudarLinguagem(i, e.target.value, sel) },
      el("option", { value: "lua", selected: i.Linguagem === "lua" }, "Lua (Luau)"),
      el("option", { value: "python", selected: i.Linguagem === "python" }, "Python"));
    linhas.push(linha("Linguagem", sel));
    linhas.push(el("p", { class: "vazio" }, `Primeira linha do script: _++linguagemprogroma++_ = ${i.Linguagem}`));
    linhas.push(el("button", { class: "destaque", onclick: () => abrirScript(i) }, "Editar script"));
  }
  if (!ehServico) {
    const destinos = [estado.mundo.workspace, estado.mundo.game.ServerScriptService, estado.mundo.game.ReplicatedStorage,
      estado.mundo.game.StarterPlayer.FindFirstChildOfClass("StarterPlayerScripts"),
      ...estado.mundo.game.GetDescendants().filter((d) => ["Model", "Folder"].includes(d.ClassName) && d !== i && !d.EhDescendenteDe(i))];
    linhas.push(linha("Parent", el("select", {
      onchange: (e) => { i.Parent = destinos[+e.target.value]; marcar(); selecionar(i); },
    }, destinos.map((d, n) => el("option", { value: n, selected: i.Parent === d }, d.GetFullName())))));
  }
  caixa.replaceChildren(...linhas);
}

function sincronizarGizmo() {
  if (gizmo?.object && estado.sel) render.atualizar(estado.sel);
}

// ------------------------------------------------------------ scripts
async function mudarLinguagem(s, lang, select) {
  if (lang === s.Linguagem) return;
  if (s.ClassName === "LocalScript" && lang === "python") {
    const continuar = await modal([
      el("p", {}, AVISO_PYTHON_LOCAL, " Para saber mais, ", el("a", { href: LINK_PYTHON, target: "_blank", rel: "noopener" }, "clique aqui"), "."),
    ], [{ texto: "Cancelar", valor: false }, { texto: "Mudar para Python mesmo assim", valor: true, destaque: true }]);
    if (!continuar) { if (select) select.value = s.Linguagem; return; }
  }
  s.definirLinguagem(lang);
  estado.sujo = true;
  if (!$("#editorScript").hidden) $("#scriptTexto").value = s.Source;
  desenharExplorer(); desenharProps(); atualizarDicaScript(s);
}

let scriptAberto = null;
function abrirScript(s) {
  scriptAberto = s;
  $("#scriptNome").textContent = `${s.Name} (${s.ClassName})`;
  $("#scriptLang").value = s.Linguagem;
  $("#scriptTexto").value = s.Source;
  atualizarDicaScript(s);
  $("#editorScript").hidden = false;
  $("#scriptTexto").focus();
}
function atualizarDicaScript(s) {
  const onde = { Script: "roda no servidor", LocalScript: "roda no dispositivo do jogador", ModuleScript: "use com require()" }[s.ClassName];
  $("#scriptDica").textContent = `${s.ClassName} ${onde}. Linguagem: ${s.Linguagem === "lua" ? "Lua (Luau)" : "Python"}` +
    (s.Linguagem === "python" ? " — use await wait(1) para esperar." : " — use wait(1) para esperar.");
}
function fecharScript() {
  if (scriptAberto) { scriptAberto.Source = $("#scriptTexto").value; estado.sujo = true; }
  scriptAberto = null; $("#editorScript").hidden = true; desenharExplorer(); desenharProps();
}
$("#scriptFechar").addEventListener("click", fecharScript);
$("#scriptLang").addEventListener("change", (e) => {
  if (!scriptAberto) return;
  scriptAberto.Source = $("#scriptTexto").value;
  mudarLinguagem(scriptAberto, e.target.value, e.target);
});
$("#scriptTexto").addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const t = e.target, a = t.selectionStart;
    t.setRangeText("  ", a, t.selectionEnd, "end");
  } else if (e.key === "Escape") fecharScript();
});

// ---------------------------------------------------------------- ações
function ondeColocar(classe) {
  const g = estado.mundo.game, s = estado.sel;
  const container = s && !s._destruida && ["Model", "Folder", "Workspace", "ServerScriptService", "ReplicatedStorage", "StarterPlayerScripts"].includes(s.ClassName) ? s : null;
  if (classe === "Script") return container && container.ClassName !== "StarterPlayerScripts" ? container : g.ServerScriptService;
  if (classe === "LocalScript") return container?.ClassName === "StarterPlayerScripts" ? container : g.StarterPlayer.FindFirstChildOfClass("StarterPlayerScripts");
  if (classe === "ModuleScript") return container || g.ReplicatedStorage;
  return container && container.IsDescendantOf?.(estado.mundo.workspace) || container?.ClassName === "Workspace" ? container : estado.mundo.workspace;
}

function posicaoNaFrente() {
  const t = orbita.target;
  return new Vector3(Math.round(t.x), Math.max(0.5, Math.round(t.y) + 0.5), Math.round(t.z));
}

function novaParte(classe, forma) {
  if (estado.mundo.contarPartes() >= LIMITE_PARTES) {
    modal(`Limite de ${LIMITE_PARTES} peças no Studio ${PESADO ? "PC" : "leve"}.` + (PESADO ? "" : " Para mapas maiores, use o Studio PC."));
    return;
  }
  const p = criar(classe);
  if (forma) { p.Shape = forma; p.Size = new Vector3(4, 4, 4); }
  p.Anchored = true;
  p.Position = posicaoNaFrente().add(new Vector3(0, p.Size.Y / 2, 0));
  p.Parent = ondeColocar(classe);
  estado.sujo = true;
  selecionar(p);
}

function novoScript(classe) {
  const s = criar(classe);
  s.Parent = ondeColocar(classe);
  estado.sujo = true;
  selecionar(s);
  abrirScript(s);
}

const acoes = {
  async novo() {
    if (estado.sujo && !(await modal("Descartar as mudanças não salvas?", [{ texto: "Cancelar", valor: false }, { texto: "Descartar", valor: true, destaque: true }]))) return;
    trocarMundo(mundoInicial(), null);
  },
  async abrir() {
    let lista = [];
    try { lista = await (await fetch("/api/projetos")).json(); } catch { /* sem servidor */ }
    if (!lista.length) { modal("Nenhum projeto salvo ainda. Use Salvar ou Importar .rolox."); return; }
    const escolha = await modal([el("p", {}, "Abrir projeto:"), el("div", { class: "lista" },
      lista.map((p) => el("button", { onclick: () => { $("#modal").hidden = true; carregarProjeto(p.nome); } },
        `${p.nome}  (${Math.ceil(p.tamanho / 1024)} KB)`)))], [{ texto: "Cancelar", valor: false }]);
    return escolha;
  },
  async salvar() {
    const nome = estado.nome || (await perguntar("Nome do projeto (letras, números, - ou _):", "meu-jogo"));
    if (!nome) return;
    const r = await fetch(`/api/projetos/${encodeURIComponent(nome)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(salvarMundo(estado.mundo, nome)),
    });
    if (!r.ok) { modal(`Não foi possível salvar: ${(await r.text()).replace(/<[^>]+>/g, " ").trim().slice(0, 200)}`); return; }
    estado.nome = nome; estado.sujo = false;
    saida(`Projeto "${nome}" salvo.`, "sistema");
  },
  exportar() {
    const nome = estado.nome || "meu-jogo";
    const blob = new Blob([JSON.stringify(salvarMundo(estado.mundo, nome))], { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `${nome}.rolox` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  },
  importarRolox() { $("#arquivoRolox").click(); },
  importarObj() { $("#arquivoObj").click(); },
  part() { novaParte("Part"); },
  bola() { novaParte("Part", "Ball"); },
  cilindro() { novaParte("Part", "Cylinder"); },
  spawn() { novaParte("SpawnLocation"); },
  script() { novoScript("Script"); },
  localscript() { novoScript("LocalScript"); },
  modulescript() { novoScript("ModuleScript"); },
  pasta() { const f = criar("Folder"); f.Parent = ondeColocar("Folder"); estado.sujo = true; selecionar(f); },
  duplicar() {
    const s = estado.sel; if (!s || s.constructor.naoCriavel) return;
    const c = s.Clone(); c.Parent = s.Parent;
    if (c instanceof BasePart) c.Position = c.Position.add(new Vector3(0, 0, s.Size.Z + 0.5));
    estado.sujo = true; selecionar(c);
  },
  apagar() {
    const s = estado.sel; if (!s || s.constructor.naoCriavel) return;
    s.Destroy(); estado.sujo = true; selecionar(null);
  },
  mover() { gizmo?.setMode("translate"); marcarBotao("mover"); },
  escalar() { gizmo?.setMode("scale"); marcarBotao("escalar"); },
  limparSaida() { $("#saida").replaceChildren(); },
  async jogar() { estado.jogo ? pararJogo() : iniciarJogo(); },
};

function marcarBotao(acao) {
  for (const b of document.querySelectorAll('[data-acao="mover"],[data-acao="escalar"]')) b.classList.toggle("ativo", b.dataset.acao === acao);
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-acao]");
  if (b && acoes[b.dataset.acao]) acoes[b.dataset.acao]();
});

$("#arquivoObj").addEventListener("change", async (e) => {
  const arquivos = e.target.files; if (!arquivos?.length) return;
  try {
    const { parte, avisos } = await importarNoMundo(estado.mundo, render, arquivos, posicaoNaFrente());
    saida(`Importado: ${parte.Name} (${parte.Size})`, "sistema");
    for (const a of avisos) saida(a, "aviso");
    estado.sujo = true; selecionar(parte);
  } catch (err) { modal(err.message); }
  e.target.value = "";
});
$("#arquivoRolox").addEventListener("change", async (e) => {
  const f = e.target.files?.[0]; if (!f) return;
  try { trocarMundo(carregarMundo(JSON.parse(await f.text())), f.name.replace(/\.(rolox|json)$/i, "").replace(/[^\w-]/g, "_").slice(0, 40)); }
  catch (err) { modal(`Arquivo inválido: ${err.message}`); }
  e.target.value = "";
});

async function carregarProjeto(nome) {
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(nome)}`);
    if (!r.ok) throw new Error(await r.text());
    trocarMundo(carregarMundo(await r.json()), nome);
    saida(`Projeto "${nome}" aberto.`, "sistema");
  } catch (err) { modal(`Não foi possível abrir: ${err.message}`); }
}

function trocarMundo(m, nome) {
  if (estado.jogo) pararJogo();
  gizmo?.detach();
  render.definirMundo(m);
  estado.mundo = m; estado.nome = nome; estado.sujo = false; estado.sel = null;
  desenharExplorer(); desenharProps();
}

// atalhos de teclado (editor)
document.addEventListener("keydown", (e) => {
  const digitando = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if (estado.jogo) {
    if (!digitando) { estado.jogo.teclas.add(e.key.toLowerCase()); if (e.key === " ") e.preventDefault(); }
    if (e.key === "Escape") pararJogo();
    return;
  }
  if (digitando) return;
  if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); acoes.salvar(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "d") { e.preventDefault(); acoes.duplicar(); }
  else if (e.key === "Delete") acoes.apagar();
  else if (e.key === "w" && PESADO) acoes.mover();
  else if (e.key === "r" && PESADO) acoes.escalar();
  else if (e.key === "F5") { e.preventDefault(); acoes.jogar(); }
});
document.addEventListener("keyup", (e) => estado.jogo?.teclas.delete(e.key.toLowerCase()));

// -------------------------------------------------------------- jogar
async function iniciarJogo() {
  if (scriptAberto) fecharScript();
  gizmo?.detach();
  orbita.enabled = false;
  $("#botaoJogar").textContent = "■ Parar";
  $("#botaoJogar").classList.add("ativo");
  saida("▶ Jogo iniciado", "sistema");
  if (!PESADO) marcarAba("painelCena");
  const jogo = new Jogo({
    mundoEditor: estado.mundo, render, saida,
    controlesExtras: () => (pc2cel && !CELULAR ? pc2cel.controles() : []),
  });
  estado.jogo = jogo;
  try { await jogo.iniciar(); }
  catch (err) { saida(`Erro ao iniciar: ${err.message}`, "erro"); pararJogo(); return; }
  $("#controlesToque").hidden = !(CELULAR || "ontouchstart" in window);
}

function pararJogo() {
  const jogo = estado.jogo; if (!jogo) return;
  jogo.parar();
  estado.jogo = null;
  render.definirMundo(estado.mundo);
  orbita.enabled = true;
  $("#controlesToque").hidden = true;
  $("#botaoJogar").textContent = "▶ Jogar";
  $("#botaoJogar").classList.remove("ativo");
  render.camera.position.set(20, 18, 24); orbita.target.set(0, 0, 0);
  saida("■ Jogo parado (as mudanças do teste foram descartadas)", "sistema");
  selecionar(estado.sel && !estado.sel._destruida ? estado.sel : null);
}

// joystick de toque + pulo
(() => {
  const base = $("#joystick"), manche = $("#manche");
  let id = null;
  const mover = (e) => {
    const r = base.getBoundingClientRect();
    let dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2), dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    const m = Math.hypot(dx, dy); if (m > 1) { dx /= m; dy /= m; }
    manche.style.transform = `translate(${dx * 40}px, ${dy * 40}px)`;
    if (estado.jogo) { estado.jogo.toque.x = dx; estado.jogo.toque.z = -dy; }
  };
  base.addEventListener("pointerdown", (e) => { id = e.pointerId; base.setPointerCapture(id); mover(e); });
  base.addEventListener("pointermove", (e) => { if (e.pointerId === id) mover(e); });
  const soltar = () => { id = null; manche.style.transform = ""; if (estado.jogo) { estado.jogo.toque.x = 0; estado.jogo.toque.z = 0; } };
  base.addEventListener("pointerup", soltar); base.addEventListener("pointercancel", soltar);
  const pulo = $("#botaoPulo");
  pulo.addEventListener("pointerdown", () => { if (estado.jogo) estado.jogo.toque.pular = true; });
  const parar = () => { if (estado.jogo) estado.jogo.toque.pular = false; };
  pulo.addEventListener("pointerup", parar); pulo.addEventListener("pointercancel", parar);
})();

// -------------------------------------------------------- abas (leve)
function marcarAba(id) {
  if (PESADO) return;
  for (const s of document.querySelectorAll("#area > section")) s.classList.toggle("visivel", s.id === id);
  for (const b of document.querySelectorAll("#abas button")) b.classList.toggle("ativo", b.dataset.aba === id);
}
document.querySelectorAll("#abas button").forEach((b) => b.addEventListener("click", () => marcarAba(b.dataset.aba)));
marcarAba("painelCena");

// ----------------------------------------------------------- PCtoCelular
let pc2cel = null;
function desenharPc2cel() {
  const caixa = $("#pc2cel");
  if (!pc2cel || pc2cel.estado === "desconectado") {
    caixa.replaceChildren(
      el("p", { class: "nota" }, "Use celulares como controle: incline o celular para o personagem andar e levante rápido para pular. " +
        "Até 5 por Bluetooth e 2 por cabo. Os dados do sensor ficam só entre o celular e este PC."),
      el("button", { class: "destaque", onclick: () => { pc2cel = pc2cel || new PCtoCelular(desenharPc2cel); pc2cel.conectar(); } }, "Ativar PCtoCelular"));
    return;
  }
  const c = pc2cel.contagem();
  caixa.replaceChildren(
    el("p", {}, "Código: ", el("span", { class: "codigo" }, pc2cel.codigo || "…")),
    el("p", { class: "nota" }, `Bluetooth ${c.bluetooth || 0}/${LIMITES.bluetooth} · Cabo ${c.cabo || 0}/${LIMITES.cabo}`),
    el("p", {}, el("b", {}, "Por cabo (USB):")),
    el("ol", {},
      el("li", {}, "Ligue a depuração USB no celular e conecte o cabo."),
      el("li", {}, "No PC: ", el("code", {}, `adb reverse tcp:${location.port || 80} tcp:${location.port || 80}`)),
      el("li", {}, "No celular, abra ", el("code", {}, pc2cel.urls[0] || `http://localhost:${location.port}/controle`))),
    el("p", {}, el("b", {}, "Por Bluetooth:")),
    el("ol", {},
      el("li", {}, "No celular, ligue a ancoragem (tethering) Bluetooth e pareie com o PC."),
      el("li", {}, "Rode o servidor com ", el("code", {}, "ROLOX_HOST=0.0.0.0"), "."),
      el("li", {}, "No celular, abra ", el("code", {}, pc2cel.urls[1] || "http://IP-DO-PC:" + location.port + "/controle"))),
    el("p", { class: "nota" }, "Se o celular não tiver sensor de movimento (ou o navegador bloquear), ele vira um controle padrão com joystick."),
    ...pc2cel.controles().map((x) => el("div", { class: "celular" }, el("span", {}, x.nome), el("span", { class: "nota" }, x.via))),
  );
}
if (PESADO && !CELULAR) { $("#painelPc2cel").hidden = false; desenharPc2cel(); }
if (PESADO && CELULAR) saida("Você abriu o Studio PC num celular. Para economizar bateria, use o Studio leve (/studio/leve).", "aviso");

// ------------------------------------------------------- rascunho local
const CHAVE_RASCUNHO = `rolox-studio-rascunho-${MODO}`;
try {
  const r = localStorage.getItem(CHAVE_RASCUNHO);
  if (r) { const d = JSON.parse(r); trocarMundo(carregarMundo(d.mundo), d.nome || null); estado.sujo = !!d.sujo; saida("Rascunho restaurado.", "sistema"); }
} catch { /* sem armazenamento ou rascunho inválido */ }
setInterval(() => {
  if (estado.jogo) return;
  try { localStorage.setItem(CHAVE_RASCUNHO, JSON.stringify({ nome: estado.nome, sujo: estado.sujo, mundo: salvarMundo(estado.mundo, estado.nome || "rascunho") })); }
  catch { /* sem espaço ou bloqueado */ }
}, 5000);

desenharExplorer();
desenharProps();
saida(`Rolox Studio ${PESADO ? "PC (pesado)" : "leve (celular)"} pronto.`, "sistema");
if (PESADO) carregarPython().catch(() => {});      // no PC já deixa o Python carregando
window.__studio = { estado, acoes, render };      // para testes e depuração
