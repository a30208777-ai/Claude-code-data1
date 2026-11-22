// ROLOX — ⚙️ ajustes do jogo (ficam salvos neste aparelho):
import { SONS_MORTE, tocarSomMorte } from "./sons_morte.js";
//   qualidade (baixa = celular fraco roda liso) · som · nomes dos jogadores · contador de FPS

export const PADRAO = { qualidade: "auto", som: true, nomes: true, fps: false, somMorte: "classico", sensibilidade: 1, inverterY: false, fpsMax: 0, lembrete: 60 };
export const LEMBRETES = { 0: "Desligado", 30: "A cada 30 min", 60: "A cada 1 hora" };
export const LIMITES_FPS = { 0: "Sem limite", 60: "60 FPS", 30: "30 FPS (economia de bateria)" };
export const QUALIDADES = { auto: "Automática", baixa: "Baixa (mais leve)", media: "Média", alta: "Alta (sombras)" };
const CHAVE = "rolox.ajustes";

export function lerAjustes(armazenamento = globalThis.localStorage) {
  try {
    const d = JSON.parse(armazenamento?.getItem(CHAVE) || "{}");
    return {
      qualidade: d.qualidade in QUALIDADES ? d.qualidade : PADRAO.qualidade,
      som: typeof d.som === "boolean" ? d.som : PADRAO.som,
      nomes: typeof d.nomes === "boolean" ? d.nomes : PADRAO.nomes,
      fps: typeof d.fps === "boolean" ? d.fps : PADRAO.fps,
      somMorte: d.somMorte in SONS_MORTE ? d.somMorte : PADRAO.somMorte,
      sensibilidade: Number.isFinite(d.sensibilidade) ? Math.min(3, Math.max(0.3, d.sensibilidade)) : PADRAO.sensibilidade,
      inverterY: typeof d.inverterY === "boolean" ? d.inverterY : PADRAO.inverterY,
      fpsMax: String(d.fpsMax) in LIMITES_FPS ? Number(d.fpsMax) : PADRAO.fpsMax,
      lembrete: String(d.lembrete) in LEMBRETES ? Number(d.lembrete) : PADRAO.lembrete,
    };
  } catch { return { ...PADRAO }; }
}

export function salvarAjustes(a, armazenamento = globalThis.localStorage) {
  try { armazenamento?.setItem(CHAVE, JSON.stringify(a)); } catch { /* sem armazenamento */ }
}

/** Quantos pixels por ponto de tela desenhar (menos = mais leve). */
export function escalaPixels(qualidade, dpr = 1, pesado = false) {
  if (qualidade === "baixa") return 0.6;
  if (qualidade === "media") return 1;
  if (qualidade === "alta") return Math.min(dpr, 2);
  return pesado ? Math.min(dpr, 2) : 1;                 // auto: o que o jogo já escolhia
}

const el = (tag, props = {}, ...filhos) => { const e = Object.assign(document.createElement(tag), props); e.append(...filhos); return e; };

export function aplicarAjustes(jogo, render, a, { camadaNomes, contador } = {}) {
  render.renderer.setPixelRatio(escalaPixels(a.qualidade, devicePixelRatio, render.pesado));
  render.renderer.shadowMap.enabled = a.qualidade === "alta" || (a.qualidade === "auto" && render.pesado);
  render.redimensionar?.();
  window.ROLOX_MUDO = !a.som;
  for (const m of document.querySelectorAll("audio, video")) m.muted = !a.som;
  if (camadaNomes) camadaNomes.style.display = a.nomes ? "" : "none";
  if (contador) contador.hidden = !a.fps;
  if (jogo) jogo.fpsMax = a.fpsMax;
  if (jogo?.cam) { jogo.cam.sensibilidade = a.sensibilidade; jogo.cam.inverterY = a.inverterY; }
}

export function ligarAjustes(jogo, render, { botao, painel, camadaNomes, contador }) {
  let a = lerAjustes();
  const linha = (rotulo, campo) => el("label", { className: "ajuste" }, el("span", { textContent: rotulo }), campo);
  const marca = (chave) => {
    const c = el("input", { type: "checkbox", checked: a[chave] });
    c.addEventListener("change", () => { a[chave] = c.checked; mudou(); });
    return c;
  };
  const qual = el("select", {}, ...Object.entries(QUALIDADES).map(([k, v]) => el("option", { value: k, textContent: v, selected: a.qualidade === k })));
  qual.addEventListener("change", () => { a.qualidade = qual.value; mudou(); });
  const morte = el("select", {}, ...Object.entries(SONS_MORTE).map(([k, v]) => el("option", { value: k, textContent: v, selected: a.somMorte === k })));
  morte.addEventListener("change", () => { a.somMorte = morte.value; mudou(); tocarSomMorte(a.somMorte); });
  jogo.aoMorrer = (_p, local) => { if (local && a.som) tocarSomMorte(a.somMorte); };
  const sens = el("input", { type: "range", min: "0.3", max: "3", step: "0.1", value: String(a.sensibilidade) });
  sens.addEventListener("input", () => { a.sensibilidade = Number(sens.value); mudou(); });
  const lim = el("select", {}, ...Object.entries(LIMITES_FPS).map(([k, v]) => el("option", { value: k, textContent: v, selected: String(a.fpsMax) === k })));
  lim.addEventListener("change", () => { a.fpsMax = Number(lim.value); mudou(); });
  const lem = el("select", {}, ...Object.entries(LEMBRETES).map(([k, v]) => el("option", { value: k, textContent: v, selected: String(a.lembrete) === k })));
  lem.addEventListener("change", () => { a.lembrete = Number(lem.value); mudou(); });
  const tempoHoje = el("span", { className: "tempo-hoje", textContent: "—" });
  painel.replaceChildren(el("b", { textContent: "⚙️ Ajustes" }),
    linha("Qualidade", qual), linha("🔊 Som", marca("som")), linha("🏷️ Nomes dos jogadores", marca("nomes")), linha("📈 Mostrar FPS", marca("fps")), linha("💀 Som ao cair", morte), linha("🎥 Sensibilidade da câmera", sens), linha("↕️ Inverter câmera", marca("inverterY")), linha("🔋 Limite de FPS", lim), linha("⏰ Lembrete de pausa", lem),
    el("div", { className: "ajuste" }, el("span", { textContent: "⏱️ Jogado hoje" }), tempoHoje));
  function mudou() { salvarAjustes(a); aplicarAjustes(jogo, render, a, { camadaNomes, contador }); }
  botao.addEventListener("click", () => { painel.hidden = !painel.hidden; botao.setAttribute("aria-expanded", String(!painel.hidden)); });
  aplicarAjustes(jogo, render, a, { camadaNomes, contador });
  // contador de FPS
  let quadros = 0, desde = performance.now();
  jogo.extras.push({ nomes() {
    if (!a.fps || !contador) return;
    quadros++;
    const agora = performance.now();
    if (agora - desde >= 1000) { contador.textContent = `${Math.round((quadros * 1000) / (agora - desde))} FPS`; quadros = 0; desde = agora; }
  } });
  return { get ajustes() { return a; }, mostrarTempo: (t) => { tempoHoje.textContent = t; } };
}
