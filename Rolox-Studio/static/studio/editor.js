// Rolox Studio — editor (interface). Modo "leve" (celular) e "pesado" (PC).

import { OrbitControls } from "three/addons/OrbitControls.js";
import { TransformControls } from "three/addons/TransformControls.js";
import {
  BasePart, BaseScript, Color3, Vector3, criar, mundoInicial, salvarMundo, carregarMundo, definirReporteDeErro, MATERIAIS,
} from "./motor.js";
import { Render } from "./render.js";
import { Jogo } from "./jogo.js";
import { importarNoMundo } from "./importar_obj.js";
import { PCtoCelular, ehCelular, LIMITES } from "./pctocelular.js";
import { carregarPython } from "./scripts.js";
import { MODELOS } from "./modelos.js";
import { TIPOS_MUNDO, gerarMundo } from "./gerador.js";
import { extrairAcoes, aplicarAcoes, resumoCena } from "./agente_ia.js";
import { ligarTela, ligarSons, ligarInternet } from "./tela_jogo.js";
import { ligarMidias } from "./midia_jogo.js";

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

// ------------------------------------------------- desfazer / refazer
const historico = { pilha: [], i: -1, restaurando: false, timer: null };
function fotografar() {
  const d = salvarMundo(estado.mundo, estado.nome || "projeto");
  delete d.assets;                      // malhas não mudam; não precisa copiar
  return JSON.stringify(d);
}
function gravarFoto() {
  clearTimeout(historico.timer); historico.timer = null;
  const foto = fotografar();
  if (foto === historico.pilha[historico.i]) return;
  historico.pilha.splice(historico.i + 1);
  historico.pilha.push(foto);
  if (historico.pilha.length > 60) historico.pilha.shift();
  historico.i = historico.pilha.length - 1;
  botoesHistorico();
}
function mudou() {
  estado.sujo = true;
  if (historico.restaurando || estado.jogo) return;
  clearTimeout(historico.timer);
  historico.timer = setTimeout(gravarFoto, 250);
}
function reiniciarHistorico() { historico.pilha = [fotografar()]; historico.i = 0; botoesHistorico(); }
function botoesHistorico() {
  const d = document.querySelector('[data-acao="desfazer"]'), r = document.querySelector('[data-acao="refazer"]');
  if (d) d.disabled = historico.i <= 0;
  if (r) r.disabled = historico.i >= historico.pilha.length - 1;
}
function acharPorCaminho(m, caminho) {
  let atual = m.game;
  for (const nome of caminho.split(".")) { atual = atual?.FindFirstChild(nome); if (!atual) return null; }
  return atual;
}
function irParaFoto(novo) {
  if (estado.jogo) return;
  if (scriptAberto) fecharScript();
  if (historico.timer) gravarFoto();
  if (novo < 0 || novo >= historico.pilha.length) return;
  const caminho = estado.sel && !estado.sel._destruida ? estado.sel.GetFullName() : null;
  historico.restaurando = true;
  const d = JSON.parse(historico.pilha[novo]);
  d.assets = estado.mundo.assets;
  const m = carregarMundo(d);
  gizmo?.detach();
  render.definirMundo(m);
  estado.mundo = m; estado.sujo = true;
  historico.i = novo;
  historico.restaurando = false;
  selecionar(caminho ? acharPorCaminho(m, caminho) : null);
  botoesHistorico();
}

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

// gerador de mundo: o botão do modal avisa qual tipo foi escolhido
document.getElementById("modal")?.addEventListener("escolheu", (e) => {
  const antes = estado.mundo.contarPartes();
  const pasta = gerarMundo(estado.mundo, e.detail);
  const novas = estado.mundo.contarPartes() - antes;
  if (estado.mundo.contarPartes() > LIMITE_PARTES) {
    pasta.Destroy();
    modal(`Esse mundo tem ${novas} peças e passaria do limite de ${LIMITE_PARTES} do Studio ${PESADO ? "PC" : "leve"}. Apague algumas peças antes.`);
    return;
  }
  mudou();
  selecionar(pasta);
  if (orbita) { orbita.target.set(0, 0, -110); render.camera.position.set(60, 70, -20); orbita.update?.(); }
  saida(`🏝️ Mundo "${pasta.Name}" gerado: ${novas} peças.`, "sistema");
});

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
    mudou();
    desenharProps();
  });
  render.cena.add(gizmo.getHelper ? gizmo.getHelper() : gizmo);
}

// Studio leve: arrastar a peça selecionada com o dedo (no plano da altura dela)
let arraste = null;
estado.arrastar = !PESADO;
const coordNorm = (e) => {
  const r = canvas.getBoundingClientRect();
  return [((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1];
};
canvas.addEventListener("pointerdown", (e) => {
  const i = estado.sel;
  if (PESADO || estado.jogo || !estado.arrastar || !(i instanceof BasePart) || i._destruida) return;
  const [x, y] = coordNorm(e);
  if (render.pegar(x, y) !== i) return;
  const ponto = render.pontoNoPlano(x, y, i.Position.Y);
  if (!ponto) return;
  arraste = { id: e.pointerId, dx: i.Position.X - ponto.x, dz: i.Position.Z - ponto.z };
  orbita.enabled = false;
  canvas.setPointerCapture(e.pointerId);
}, { capture: true });
canvas.addEventListener("pointermove", (e) => {
  if (!arraste || e.pointerId !== arraste.id) return;
  const i = estado.sel, [x, y] = coordNorm(e);
  const ponto = render.pontoNoPlano(x, y, i.Position.Y);
  if (!ponto) return;
  const passo = 0.5, arred = (v) => Math.round(v / passo) * passo;
  i.Position = new Vector3(arred(ponto.x + arraste.dx), i.Position.Y, arred(ponto.z + arraste.dz));
});
const fimArraste = (e) => {
  if (!arraste || e.pointerId !== arraste.id) return false;
  arraste = null; orbita.enabled = true; mudou(); desenharProps();
  return true;
};
canvas.addEventListener("pointercancel", fimArraste);

// clique/toque na cena seleciona
let inicioToque = null;
canvas.addEventListener("pointerdown", (e) => { inicioToque = [e.clientX, e.clientY]; });
canvas.addEventListener("pointerup", (e) => {
  if (fimArraste(e)) { inicioToque = null; return; }
  if (estado.jogo || !inicioToque) return;
  const movimento = Math.hypot(e.clientX - inicioToque[0], e.clientY - inicioToque[1]);
  inicioToque = null;
  if (movimento > 6 || gizmo?.dragging) return;
  const r = canvas.getBoundingClientRect();
  const alvo = render.pegar(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  if (pincel.ativo) {                                     // 🎨 pincel: pinta em vez de selecionar
    if (alvo instanceof BasePart && !alvo._temporaria) pintar(alvo);
    return;
  }
  selecionar(alvo && !alvo._temporaria ? alvo : null);
});

// ----------------------------------------------------------- 🎨 pincel
const pincel = { ativo: false, cor: "#ff7043", material: "Plastico", pintadas: 0 };
function pintar(p) {
  p.Color = Color3.fromHex(pincel.cor);
  if (pincel.material) p.Material = pincel.material;
  pincel.pintadas++;
  mudou();
  if (estado.sel === p) desenharProps();
}
function paletaPincel() {
  let caixa = document.getElementById("paletaPincel");
  if (!caixa) {
    const cor = el("input", { type: "color", value: pincel.cor, "aria-label": "Cor do pincel",
      oninput: (e) => { pincel.cor = e.target.value; } });
    const mat = el("select", { "aria-label": "Material do pincel", onchange: (e) => { pincel.material = e.target.value; } },
      MATERIAIS.map((m) => el("option", { value: m, selected: m === pincel.material }, NOMES_MATERIAIS[m] || m)));
    caixa = el("div", { id: "paletaPincel", class: "paleta-pincel", hidden: true },
      el("b", {}, "🎨 Pincel"), cor, mat,
      el("span", { class: "vazio" }, "Toque nas peças para pintar"),
      el("button", { class: "destaque", onclick: () => ligarPincel(false) }, "✓ Pronto"));
    canvas.parentElement.append(caixa);
  }
  return caixa;
}
function ligarPincel(sim) {
  pincel.ativo = sim;
  paletaPincel().hidden = !sim;
  document.querySelector('[data-acao="pincel"]')?.classList.toggle("ativo", sim);
  if (sim) { selecionar(null); saida("🎨 Pincel ligado: toque nas peças para pintar.", "sistema"); }
  else if (pincel.pintadas) { saida(`🎨 ${pincel.pintadas} peça(s) pintada(s).`, "sistema"); pincel.pintadas = 0; }
}

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
  Workspace: "🌍", Part: "▫️", SpawnLocation: "🟩", Checkpoint: "🚩", MeshPart: "🧊", Model: "📦", Folder: "📁",
  Script: "🐍", LocalScript: "📜", ModuleScript: "🧩", ServerScriptService: "🖥️", ReplicatedStorage: "🗄️",
  StarterPlayer: "🧍", StarterPlayerScripts: "📂", Rede: "📡", Cofre: "🔐", Tela: "🖥️", Sons: "🔊", Emblemas: "🏅", Internet: "🌐", Ceu: "🌤️", Animar: "🎞️", Efeitos: "✨", Som: "🎵", TelaVideo: "🎬", IntValue: "🔢", NumberValue: "🔢",
};
const SERVICOS_VISIVEIS = ["Workspace", "ServerScriptService", "ReplicatedStorage", "StarterPlayer", "Ceu"];
const NOMES_MATERIAIS = { Plastico: "Plástico", Agua: "Água" };

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
  const marcar = () => { mudou(); desenharExplorer(); };
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
    else if (p === "Material") {
      linhas.push(linha("Material", el("select", { onchange: (e) => { i.Material = e.target.value; marcar(); } },
        MATERIAIS.map((m) => el("option", { value: m, selected: m === v }, NOMES_MATERIAIS[m] || m)))));
    } else if (p === "Shape") {
      linhas.push(linha(p, el("select", { onchange: (e) => { i.Shape = e.target.value; i._mudou("Shape"); marcar(); } },
        ["Block", "Ball", "Cylinder"].map((s) => el("option", { value: s, selected: s === v }, { Block: "Bloco", Ball: "Bola", Cylinder: "Cilindro" }[s])))));
    } else if (typeof v === "number") {
      linhas.push(linha(p, el("input", { type: "number", step: p === "Transparency" || p === "Neblina" ? "0.1" : "1", value: v,
        onchange: (e) => { i[p] = +e.target.value; marcar(); } })));
    } else if (p === "MeshId") linhas.push(linha(p, el("input", { type: "text", value: v, readonly: true })));
    else if (p === "Midia") linhas.push(linha("Arquivo", el("input", { type: "text", value: v || "(nenhum)", readonly: true })));
  }
  if (i instanceof BasePart && !PESADO) {
    const mexer = (dy, giro = 0) => () => {
      i.Position = i.Position.add(new Vector3(0, dy, 0));
      if (giro) i.Rotation = i.Rotation.add(new Vector3(0, giro, 0));
      mudou(); desenharProps();
    };
    linhas.splice(1, 0, el("p", { class: "vazio" }, "Arraste a peça na cena com o dedo para mover."),
      el("div", { class: "botoesLeve" },
        el("button", { onclick: mexer(1) }, "⬆ Subir"), el("button", { onclick: mexer(-1) }, "⬇ Descer"),
        el("button", { onclick: mexer(0, 45) }, "⟳ Girar 45°")));
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
  mudou();
  if (!$("#editorScript").hidden) { $("#scriptTexto").value = s.Source; atualizarRealce(); }
  desenharExplorer(); desenharProps(); atualizarDicaScript(s);
}

// realce de sintaxe (camada colorida atrás da caixa de texto)
const PALAVRAS = {
  lua: new Set("and break do else elseif end false for function goto if in local nil not or repeat return then true until while continue type export".split(" ")),
  python: new Set("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(" ")),
};
const API = new Set("game workspace Workspace script Instance Vector3 Color3 wait task print warn require spawn delay math string table pairs ipairs tostring tonumber self len range str int float list dict".split(" "));
const RE_TOKENS = {
  lua: /(?<com>--\[(?<eqc>=*)\[[\s\S]*?\]\k<eqc>\]|--[^\n]*)|(?<txt>"(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?|`(?:[^`\\]|\\.)*`?|\[(?<eqs>=*)\[[\s\S]*?\]\k<eqs>\])|(?<num>\b0x[\da-fA-F]+\b|\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(?<nome>[A-Za-z_]\w*)/g,
  python: /(?<com>#[^\n]*)|(?<txt>(?:\b[rbfRBF]{1,2})?(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?))|(?<num>\b0x[\da-fA-F]+\b|\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(?<nome>[A-Za-z_]\w*)/g,
};
const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function realcar(codigo, lang) {
  let html = "", ultimo = 0;
  const re = RE_TOKENS[lang] || RE_TOKENS.lua;
  re.lastIndex = 0;
  for (let m; (m = re.exec(codigo)); ) {
    if (m[0] === "") { re.lastIndex++; continue; }
    html += esc(codigo.slice(ultimo, m.index));
    const v = m[0];
    let classe = "";
    const g = m.groups;
    if (g.com) classe = "tk-com"; else if (g.txt) classe = "tk-txt"; else if (g.num) classe = "tk-num";
    else if (g.nome) classe = PALAVRAS[lang]?.has(v) ? "tk-kw" : API.has(v) ? "tk-api" : "";
    html += classe ? `<span class="${classe}">${esc(v)}</span>` : esc(v);
    ultimo = m.index + v.length;
  }
  html += esc(codigo.slice(ultimo));
  // a diretiva de linguagem em destaque
  html = html.replace(/^(\s*)(_\+\+linguagemprogroma\+\+_)/m, '$1<span class="tk-dir">$2</span>');
  return html + "\n";
}
function atualizarRealce() {
  const t = $("#scriptTexto"), lang = scriptAberto?.Linguagem || "lua";
  $("#realce code").innerHTML = realcar(t.value, lang);
  const linhas = t.value.split("\n").length;
  $("#numeros").textContent = Array.from({ length: linhas }, (_, k) => k + 1).join("\n") + "\n";
  sincronizarRolagem();
}
function sincronizarRolagem() {
  const t = $("#scriptTexto");
  $("#realce").scrollTop = t.scrollTop; $("#realce").scrollLeft = t.scrollLeft; $("#numeros").scrollTop = t.scrollTop;
}

let scriptAberto = null;
function abrirScript(s) {
  scriptAberto = s;
  $("#scriptNome").textContent = `${s.Name} (${s.ClassName})`;
  $("#scriptLang").value = s.Linguagem;
  $("#scriptTexto").value = s.Source;
  atualizarDicaScript(s);
  $("#editorScript").hidden = false;
  atualizarRealce();
  $("#scriptTexto").focus();
}
function atualizarDicaScript(s) {
  const onde = { Script: "roda no servidor", LocalScript: "roda no dispositivo do jogador", ModuleScript: "use com require()" }[s.ClassName];
  $("#scriptDica").textContent = `${s.ClassName} ${onde}. Linguagem: ${s.Linguagem === "lua" ? "Lua (Luau)" : "Python"}` +
    (s.Linguagem === "python" ? " — use await wait(1) para esperar." : " — use wait(1) para esperar.");
}
function fecharScript() {
  if (scriptAberto) { scriptAberto.Source = $("#scriptTexto").value; mudou(); }
  scriptAberto = null; $("#editorScript").hidden = true; desenharExplorer(); desenharProps();
}
$("#scriptFechar").addEventListener("click", fecharScript);
$("#scriptLang").addEventListener("change", (e) => {
  if (!scriptAberto) return;
  scriptAberto.Source = $("#scriptTexto").value;
  mudarLinguagem(scriptAberto, e.target.value, e.target);
});
$("#scriptTexto").addEventListener("input", atualizarRealce);
$("#scriptTexto").addEventListener("scroll", sincronizarRolagem);
$("#scriptTexto").addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const t = e.target, a = t.selectionStart;
    t.setRangeText("  ", a, t.selectionEnd, "end");
    atualizarRealce();
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
  mudou();
  selecionar(p);
}

function novoScript(classe) {
  const s = criar(classe);
  s.Parent = ondeColocar(classe);
  mudou();
  selecionar(s);
  abrirScript(s);
}

const acoes = {
  async novo() {
    if (estado.sujo && !(await modal("Descartar as mudanças não salvas?", [{ texto: "Cancelar", valor: false }, { texto: "Descartar", valor: true, destaque: true }]))) return;
    const escolha = await modal([el("p", {}, el("b", {}, "Começar com qual modelo?")), el("div", { class: "lista" },
      MODELOS.map((x) => el("button", { class: "modelo", onclick: () => { $("#modal").hidden = true; usarModelo(x); } },
        el("b", {}, x.nome), el("span", { class: "vazio" }, x.descricao))))], [{ texto: "Cancelar", valor: false }]);
    return escolha;
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
  /** Site do ROLOX: manda o mapa para o bucket; o dono testa e aprova. */
  async enviarRolox() {
    if (estado.jogo) pararJogo();
    const csrf = document.querySelector('meta[name="csrf"]')?.content;
    if (!csrf) { modal("Enviar ao ROLOX só funciona no site."); return; }
    const nome = await perguntar("Nome do jogo (aparece na lista de Jogos):", estado.nome || "Meu jogo");
    if (!nome) return;
    const descricao = await perguntar("Descrição curta (opcional):", "");
    if (descricao === null) return;
    const chave = "rolox-mapa-" + (estado.nome || nome);
    let mapaId = null;
    try { mapaId = localStorage.getItem(chave); } catch { /* sem armazenamento */ }
    saida("Enviando o mapa...", "sistema");
    try {
      const r = await fetch("/api/mapas/enviar", {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
        body: JSON.stringify({ mapa_id: mapaId, nome, descricao, projeto: salvarMundo(estado.mundo, nome) }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.mensagem || `erro ${r.status}`);
      try { localStorage.setItem(chave, d.id); } catch { /* ok */ }
      saida(`Mapa "${nome}" enviado! O dono vai testar e aprovar.`, "sistema");
      modal(`🚀 "${nome}" foi enviado para o dono do ROLOX. Quando ele aprovar, aparece em Jogos para todo mundo. ` +
            `Se mandar de novo, a versão nova substitui a que está em análise.`);
    } catch (err) { modal(`Não foi possível enviar: ${err.message}`); }
  },
  /** Site: envia um som ou vídeo (bucket "midias") e cria o Som / TelaVideo no mapa. */
  midia() {
    const csrf = document.querySelector('meta[name="csrf"]')?.content;
    if (!csrf) { modal("Sons e vídeos só podem ser enviados pelo Studio do site."); return; }
    const inp = el("input", { type: "file", accept: "audio/mpeg,audio/ogg,audio/wav,audio/webm,video/mp4,video/webm" });
    inp.addEventListener("change", async () => {
      const f = inp.files[0]; if (!f) return;
      if (f.size > 20 * 1024 * 1024) { modal("Arquivo grande demais (máximo 20 MB; som até 5 MB)."); return; }
      saida(`Enviando ${f.name}...`, "sistema");
      const dados = new FormData(); dados.append("arquivo", f);
      try {
        const r = await fetch("/api/midias", { method: "POST", headers: { "X-CSRF": csrf }, body: dados });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.mensagem || `erro ${r.status}`);
        const i = criar(d.tipo === "video" ? "TelaVideo" : "Som");
        i.Name = (f.name.replace(/\.[^.]+$/, "").replace(/[^\w À-ÿ-]/g, "").slice(0, 30)) || i.ClassName;
        i.Midia = d.midia;
        if (d.tipo === "video") { i.Position = posicaoNaFrente().add(new Vector3(0, 3, 0)); }
        i.Parent = estado.mundo.workspace;
        mudou(); desenharExplorer(); selecionar(i);
        saida(`${d.tipo === "video" ? "🎬 Vídeo" : "🎵 Som"} "${i.Name}" pronto. Use ${i.Name}:Tocar() num script (ou marque TocarAoComecar).`, "sistema");
      } catch (err) { modal(`Não deu para enviar: ${err.message}`); }
    });
    inp.click();
  },
  ia() {
    const p = $("#painelIA");
    if (!p) return;
    p.hidden = !p.hidden;
    if (!p.hidden) $("#iaTexto").focus();
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
  async gerarMundo() {
    const tipo = await modal([el("p", {}, el("b", {}, "🏝️ Gerar um mundo pronto")),
      el("p", { class: "vazio" }, "Vai para uma pasta no Workspace, na frente do spawn. Dá para desfazer (↶)."),
      el("div", { class: "lista" }, Object.entries(TIPOS_MUNDO).map(([k, t]) => el("button", {
        class: "modelo", onclick: () => { $("#modal").hidden = true; $("#modal").dispatchEvent(new CustomEvent("escolheu", { detail: k })); },
      }, el("b", {}, t.nome), el("span", { class: "vazio" }, t.descricao))))], [{ texto: "Cancelar", valor: false }]);
    void tipo;
  },
  pincel() { ligarPincel(!pincel.ativo); },
  part() { novaParte("Part"); },
  bola() { novaParte("Part", "Ball"); },
  cilindro() { novaParte("Part", "Cylinder"); },
  spawn() { novaParte("SpawnLocation"); },
  checkpoint() { novaParte("Checkpoint"); },
  script() { novoScript("Script"); },
  localscript() { novoScript("LocalScript"); },
  modulescript() { novoScript("ModuleScript"); },
  pasta() { const f = criar("Folder"); f.Parent = ondeColocar("Folder"); mudou(); selecionar(f); },
  duplicar() {
    const s = estado.sel; if (!s || s.constructor.naoCriavel) return;
    const c = s.Clone(); c.Parent = s.Parent;
    if (c instanceof BasePart) c.Position = c.Position.add(new Vector3(0, 0, s.Size.Z + 0.5));
    mudou(); selecionar(c);
  },
  apagar() {
    const s = estado.sel; if (!s || s.constructor.naoCriavel) return;
    s.Destroy(); mudou(); selecionar(null);
  },
  mover() { gizmo?.setMode("translate"); marcarBotao("mover"); },
  escalar() { gizmo?.setMode("scale"); marcarBotao("escalar"); },
  limparSaida() { $("#saida").replaceChildren(); },
  desfazer() { irParaFoto(historico.i - 1); },
  refazer() { irParaFoto(historico.i + 1); },
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
    mudou(); selecionar(parte);
  } catch (err) { modal(err.message); }
  e.target.value = "";
});
$("#arquivoRolox").addEventListener("change", async (e) => {
  const f = e.target.files?.[0]; if (!f) return;
  try { trocarMundo(carregarMundo(JSON.parse(await f.text())), f.name.replace(/\.(rolox|json)$/i, "").replace(/[^\w-]/g, "_").slice(0, 40)); }
  catch (err) { modal(`Arquivo inválido: ${err.message}`); }
  e.target.value = "";
});

function usarModelo(x) {
  trocarMundo(x.criar(), null);
  if (x.id !== "vazio") { mudou(); saida(`Modelo "${x.nome}" criado. Aperte ▶ Jogar para testar.`, "sistema"); }
}

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
  reiniciarHistorico();
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
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); acoes.desfazer(); }
  else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); acoes.refazer(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); acoes.salvar(); }
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
  jogo._camadaTela = ligarTela(jogo, $("#painelCena"));
  if (document.querySelector('meta[name="csrf"]')) ligarInternet(jogo);      // Studio do site
  jogo._pararMusica = ligarSons(jogo);
  try { await jogo.iniciar(); }
  catch (err) { saida(`Erro ao iniciar: ${err.message}`, "erro"); pararJogo(); return; }
  jogo._pararMidias = ligarMidias(jogo, render);
  $("#controlesToque").hidden = !(CELULAR || "ontouchstart" in window);
}

function pararJogo() {
  const jogo = estado.jogo; if (!jogo) return;
  jogo.parar();
  jogo._camadaTela?.remove(); jogo._pararMusica?.(); jogo._pararMidias?.();
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
if (!historico.pilha.length) reiniciarHistorico();

// abrir direto pelo endereço (o app Rolox usa isso):
//   /studio/leve?projeto=meu-jogo     abre um projeto salvo
//   /studio/leve?modelo=obby          começa com um modelo (vazio, obby, moedas)
(() => {
  const p = new URLSearchParams(location.search);
  const projeto = p.get("projeto"), modelo = p.get("modelo");
  if (projeto && /^[A-Za-z0-9_-]{1,40}$/.test(projeto)) carregarProjeto(projeto);
  else if (modelo) { const x = MODELOS.find((m) => m.id === modelo); if (x) usarModelo(x); }
  if (projeto || modelo) history.replaceState(null, "", location.pathname);   // recarregar não repete
})();
saida(`Rolox Studio ${PESADO ? "PC (pesado)" : "leve (celular)"} pronto.`, "sistema");
if (PESADO) carregarPython().catch(() => {});      // no PC já deixa o Python carregando
window.__studio = { estado, acoes, render };      // para testes e depuração

// ------------------------------------------------------------ IA do Studio (site)
(() => {
  const form = $("#iaForm");
  if (!form) return;
  const caixa = $("#iaMensagens"), campo = $("#iaTexto"), botao = $("#iaEnviar");
  const csrf = document.querySelector('meta[name="csrf"]')?.content;
  const historico = [];

  // texto da IA: blocos ```código``` viram caixas com Copiar / Colar no script
  function mostrar(texto, quem, modelo) {
    const bolha = el("div", { class: `msgIA ${quem}` });
    const partes = texto.split(/```[a-zA-Z]*\n?/);
    partes.forEach((parte, i) => {
      if (!parte.trim()) return;
      if (i % 2 === 1) {
        const pre = el("pre", {}, parte.replace(/\n$/, ""));
        const copiar = el("button", { class: "mini", onclick: () => navigator.clipboard?.writeText(pre.textContent) }, "📋 Copiar");
        const colar = el("button", { class: "mini", onclick: () => colarNoScript(pre.textContent) }, "➕ Colar no script aberto");
        bolha.append(pre, el("div", { class: "botoesCodigo" }, copiar, colar));
      } else {
        // **negrito** vira <b> (montado com nós de texto: a resposta nunca vira HTML)
        const p = el("p", {});
        parte.trim().split(/\*\*(.+?)\*\*/g).forEach((pedaco, j) => {
          if (pedaco) p.append(j % 2 ? el("b", {}, pedaco) : document.createTextNode(pedaco));
        });
        bolha.append(p);
      }
    });
    if (modelo) bolha.append(el("small", { class: "vazio" }, modelo));
    caixa.append(bolha);
    caixa.scrollTop = caixa.scrollHeight;
  }

  // a IA põe a mão na massa: cria/edita peças e scripts direto no mapa (↶ desfaz tudo de uma vez)
  async function executarAcoesDaIA(acoes) {
    if (estado.jogo) pararJogo();
    const confirmar = (texto) => modal(texto, [{ texto: "Não", valor: false }, { texto: "Pode apagar", valor: true, destaque: true }]);
    const { log, criados } = await aplicarAcoes(estado.mundo, acoes, { confirmar, limitePartes: LIMITE_PARTES });
    mudou();
    desenharExplorer();
    const peca = criados.find((c) => c instanceof BasePart) || criados[0];
    if (peca && !peca._destruida) selecionar(peca);
    if (scriptAberto && !scriptAberto._destruida) { $("#scriptTexto").value = scriptAberto.Source; atualizarRealce(); }
    const bolha = el("div", { class: "msgIA acoes" }, el("b", {}, "O que a IA fez no mapa:"),
      ...log.map((l) => el("div", {}, l)),
      el("small", { class: "vazio" }, "Não gostou? Use ↶ (Desfazer)."));
    caixa.append(bolha);
    caixa.scrollTop = caixa.scrollHeight;
    log.forEach((l) => saida("IA: " + l, "sistema"));
  }

  function colarNoScript(codigo) {
    if (!scriptAberto) { modal("Abra um Script ou LocalScript (no Explorer) e toque de novo em ➕."); return; }
    const t = $("#scriptTexto");
    t.value = t.value.trimEnd() + (t.value.trim() ? "\n\n" : "") + codigo + "\n";
    scriptAberto.Source = t.value; mudou(); atualizarRealce();
    saida("Código da IA colado no script " + scriptAberto.Name, "sistema");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const texto = campo.value.trim();
    if (!texto || botao.disabled) return;
    historico.push({ role: "user", content: texto });
    mostrar(texto, "eu");
    campo.value = "";
    botao.disabled = true; botao.textContent = "Pensando...";
    try {
      const r = await fetch("/api/studio/ia", {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
        body: JSON.stringify({ mensagens: historico, cena: resumoCena(estado.mundo) }),
      });
      const d = await r.json().catch(() => ({}));
      if (d.tickets !== undefined && d.tickets !== null) $("#iaTickets").textContent = "🎟️ " + d.tickets;
      if (!r.ok) {
        historico.pop();
        mostrar(d.mensagem || `Erro ${r.status}`, "erro");
        return;
      }
      historico.push({ role: "assistant", content: d.resposta });
      const { acoes, texto: explicacao, erro } = extrairAcoes(d.resposta);
      mostrar(explicacao || "Feito!", "ia", d.modelo);
      if (erro) mostrar(erro, "erro");
      if (acoes.length) await executarAcoesDaIA(acoes);
    } catch {
      historico.pop();
      mostrar("Sem conexão com o site. Tente de novo.", "erro");
    } finally { botao.disabled = false; botao.textContent = "Enviar"; }
  });
  campo.addEventListener("keydown", (e) => {
    e.stopPropagation();                                   // atalhos do editor não disparam enquanto digita
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
})();
