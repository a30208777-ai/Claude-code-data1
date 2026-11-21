// ROLOX — desenha a Tela (textos, botões, barras, avisos) e toca os Sons do jogo.
// Os sons são SINTETIZADOS na hora (Web Audio): nada de arquivo, nada de direito autoral.

/** Internet pelo servidor do ROLOX (só funciona aberto pelo site). */
export function ligarInternet(jogo, url = "/api/internet") {
  jogo.mundo.game.Internet._buscar = async (termo) => {
    const r = await fetch(`${url}?q=${encodeURIComponent(termo)}`, { cache: "no-store" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.mensagem || `erro ${r.status}`);
    return d;
  };
}

export function ligarTela(jogo, container) {
  const tela = jogo.mundo.game.Tela;
  // emblema ganho: aviso + som (no jogo do site e no Studio)
  jogo.mundo.game.Emblemas.Ganhou.Connect((codigo, nome, emoji) => {
    tela.Aviso(`${emoji} Emblema ganho: ${nome}`, 4);
    try { jogo.mundo.game.Sons.Tocar("vitoria"); } catch { /* sem som */ }
  });
  const camada = document.createElement("div");
  camada.className = "tela-rolox";
  const lugares = {};
  for (const l of ["topo", "centro", "baixo", "esquerda", "direita"]) {
    const d = document.createElement("div"); d.className = `tela-lugar tela-${l}`; camada.append(d); lugares[l] = d;
  }
  container.append(camada);
  const els = new Map();

  tela.Mudou.Connect((id, item) => {
    els.get(id)?.remove(); els.delete(id);
    if (!item) return;
    let el;
    if (item.tipo === "botao") {
      el = document.createElement("button");
      el.className = "tela-botao"; el.textContent = item.texto;
      el.addEventListener("pointerdown", (e) => e.stopPropagation());
      el.addEventListener("click", (e) => { e.stopPropagation(); tela._clicar(id); el.blur(); });
    } else if (item.tipo === "barra") {
      el = document.createElement("div"); el.className = "tela-barra";
      const cheio = document.createElement("div"); cheio.style.width = `${(100 * item.valor) / item.maximo}%`;
      const rot = document.createElement("span"); rot.textContent = `${id}: ${Math.round(item.valor)}/${item.maximo}`;
      el.append(cheio, rot);
    } else {
      el = document.createElement("div");
      el.className = item.tipo === "aviso" ? "tela-aviso" : "tela-texto";
      el.textContent = item.texto;                      // texto puro: nunca vira HTML
    }
    els.set(id, el);
    lugares[item.lugar]?.append(el);
  });
  return camada;
}

// ------------------------------------------------------------------ sons
let ctx = null;
function audio() {
  if (globalThis.window?.ROLOX_MUDO) return null;        // ⚙️ som desligado nos ajustes
  if (!ctx) {
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return null;
    ctx = new C();
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

function nota(a, freq, inicio, dur, tipo = "square", vol = 0.12, freqFim = null) {
  const o = a.createOscillator(), g = a.createGain();
  o.type = tipo;
  o.frequency.setValueAtTime(freq, inicio);
  if (freqFim) o.frequency.exponentialRampToValueAtTime(freqFim, inicio + dur);
  g.gain.setValueAtTime(vol, inicio);
  g.gain.exponentialRampToValueAtTime(0.0001, inicio + dur);
  o.connect(g).connect(a.destination);
  o.start(inicio); o.stop(inicio + dur + 0.02);
}

function ruido(a, inicio, dur, vol = 0.3) {
  const n = Math.floor(a.sampleRate * dur), buf = a.createBuffer(1, n, a.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n);
  const s = a.createBufferSource(), g = a.createGain();
  s.buffer = buf; g.gain.value = vol; s.connect(g).connect(a.destination); s.start(inicio);
}

export const RECEITAS = {
  moeda: (a, t) => { nota(a, 988, t, 0.08); nota(a, 1319, t + 0.08, 0.25); },
  pulo: (a, t) => nota(a, 300, t, 0.18, "square", 0.1, 700),
  vitoria: (a, t) => [523, 659, 784, 1047].forEach((f, i) => nota(a, f, t + i * 0.12, i === 3 ? 0.5 : 0.14, "triangle", 0.18)),
  dano: (a, t) => nota(a, 220, t, 0.3, "sawtooth", 0.12, 80),
  clique: (a, t) => nota(a, 1200, t, 0.04, "square", 0.06),
  porta: (a, t) => { nota(a, 140, t, 0.35, "sawtooth", 0.08, 90); ruido(a, t, 0.25, 0.08); },
  explosao: (a, t) => { ruido(a, t, 0.8, 0.5); nota(a, 90, t, 0.6, "sine", 0.4, 30); },
  erro: (a, t) => { nota(a, 196, t, 0.15, "square", 0.1); nota(a, 147, t + 0.17, 0.25, "square", 0.1); },
};

const MELODIAS = {
  calma: { bpm: 84, tipo: "triangle", vol: 0.05, notas: [262, 330, 392, 330, 294, 349, 440, 349, 262, 330, 392, 523, 494, 392, 330, 294] },
  acao: { bpm: 150, tipo: "square", vol: 0.04, notas: [330, 330, 392, 330, 294, 294, 349, 294, 262, 262, 330, 262, 247, 294, 392, 494] },
};

export function ligarSons(jogo) {
  const sons = jogo.mundo.game.Sons;
  let musica = null;
  const pararMusica = () => { if (musica) { clearInterval(musica); musica = null; } };
  sons.Tocou.Connect((tipo, nome) => {
    const a = audio();
    if (!a) return;
    if (tipo === "som") RECEITAS[nome]?.(a, a.currentTime + 0.01);
    else {
      pararMusica();
      const m = MELODIAS[nome];
      if (!m) return;
      let i = 0;
      const passo = 60 / m.bpm;
      musica = setInterval(() => {
        if (!jogo.rodando) { pararMusica(); return; }
        const f = m.notas[i++ % m.notas.length];
        nota(a, f, a.currentTime + 0.01, passo * 0.9, m.tipo, m.vol);
        if (i % 4 === 1) nota(a, f / 2, a.currentTime + 0.01, passo * 1.8, "sine", m.vol * 0.8);
      }, passo * 1000);
    }
  });
  return pararMusica;
}
