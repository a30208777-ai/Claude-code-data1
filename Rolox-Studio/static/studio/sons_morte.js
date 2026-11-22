// ROLOX — 💀 som de quando o seu personagem cai: VOCÊ escolhe (e nunca vamos tirar o seu favorito).
// Todos são gerados na hora (Web Audio), sem arquivo para baixar.

export const SONS_MORTE = { classico: "Clássico (uuf!)", pop: "Pop", sino: "Sino", robo: "Robô", nenhum: "Nenhum" };

let ctx = null;
function audio() {
  const C = globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!C) return null;
  ctx ??= new C();
  return ctx;
}

/** Notas de cada som: [frequência inicial, final, duração, forma]. */
export function receita(nome) {
  return {
    classico: [[420, 160, 0.22, "sawtooth"]],
    pop: [[900, 120, 0.08, "sine"]],
    sino: [[880, 880, 0.5, "sine"], [1320, 1320, 0.4, "sine"]],
    robo: [[300, 300, 0.1, "square"], [200, 200, 0.1, "square"], [120, 120, 0.18, "square"]],
  }[nome] ?? [];
}

export function tocarSomMorte(nome) {
  if (globalThis.ROLOX_MUDO) return false;
  const notas = receita(nome);
  const a = notas.length && audio();
  if (!a) return false;
  let t = a.currentTime;
  for (const [f0, f1, dur, forma] of notas) {
    const o = a.createOscillator(), g = a.createGain(), filtro = a.createBiquadFilter();
    o.type = forma; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    filtro.type = "lowpass"; filtro.frequency.value = 1800;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(Math.max(0.0002, 0.3 * (globalThis.ROLOX_VOLUME ?? 1)), t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(filtro).connect(g).connect(a.destination); o.start(t); o.stop(t + dur + 0.02);
    if (nome !== "sino") t += dur;
  }
  return true;
}
