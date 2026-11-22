// ROLOX — 💧 lembrete de pausa: a cada 1 hora jogando, um aviso amigável. E o tempo jogado hoje
// (fica só neste aparelho).

export const INTERVALO_MIN = 60;
const CHAVE = "rolox.tempo_hoje";
export const MENSAGENS = [
  "💧 Você está jogando há {h}. Que tal beber água e descansar os olhos?",
  "🧘 Já faz {h} de jogo! Levanta, estica o corpo e volta com tudo.",
  "👀 {h} jogando! Olha um pouco pela janela e depois continua.",
];

export function hoje(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function textoTempo(min) {
  min = Math.max(0, Math.floor(min));
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60;
  return m ? `${h} h ${m} min` : `${h} ${h === 1 ? "hora" : "horas"}`;
}

/** Minutos jogados hoje (zera quando o dia muda). */
export function lerTempo(arm = globalThis.localStorage, dia = hoje()) {
  try {
    const d = JSON.parse(arm?.getItem(CHAVE) || "{}");
    return d.dia === dia && Number.isFinite(d.min) ? d.min : 0;
  } catch { return 0; }
}
export function somarTempo(min, arm = globalThis.localStorage, dia = hoje()) {
  const total = lerTempo(arm, dia) + min;
  try { arm?.setItem(CHAVE, JSON.stringify({ dia, min: total })); } catch { /* sem armazenamento */ }
  return total;
}

/** Texto do lembrete para N minutos desta sessão (ou null se ainda não é hora). */
export function lembrete(minSessao, jaAvisados, intervalo = INTERVALO_MIN) {
  if (!intervalo) return null;                           // ⚙️ lembrete desligado
  const marco = Math.floor(minSessao / intervalo);
  if (marco < 1 || marco <= jaAvisados) return null;
  return MENSAGENS[(marco - 1) % MENSAGENS.length].replace("{h}", textoTempo(marco * intervalo));
}

export function ligarPausa(jogo, { mostrarTempo = () => {}, intervalo = () => INTERVALO_MIN } = {}) {
  let sessao = 0, avisados = 0;
  const umMinuto = setInterval(() => {
    if (!jogo.rodando || document.hidden) return;        // só conta com o jogo aberto e na tela
    sessao += 1;
    mostrarTempo(textoTempo(somarTempo(1)));
    const iv = intervalo();
    const t = lembrete(sessao, avisados, iv);
    if (t) { avisados = Math.floor(sessao / iv); try { jogo.mundo.game.Tela.Aviso(t, 8); } catch { /* sem tela */ } }
  }, 60_000);
  mostrarTempo(textoTempo(lerTempo()));
  return () => clearInterval(umMinuto);
}
