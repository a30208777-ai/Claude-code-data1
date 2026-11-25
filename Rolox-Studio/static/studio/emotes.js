// VISTA — 😀 gestos (emotes): um balão em cima da cabeça por 4 s, que os outros jogadores também veem.
// Só os gestos desta lista (o site recusa qualquer outro valor). 💃 dançar gira o personagem e
// 🎉 comemorar dá um pulo com confete.

export const EMOTES = {
  acenar: "👋", dancar: "💃", comemorar: "🎉", rir: "😂",
  triste: "😢", bravo: "😠", coracao: "❤️", pensar: "🤔",
};
export const DURACAO_MS = 4000;

const el = (tag, props = {}, ...filhos) => { const e = Object.assign(document.createElement(tag), props); e.append(...filhos); return e; };

/** Estado do gesto (sem DOM: dá para testar). */
export class Gestos {
  constructor(agora = () => performance.now()) { this.agora = agora; this.nome = null; this.ate = 0; }
  fazer(nome) {
    if (!(nome in EMOTES)) throw new Error(`gesto desconhecido: ${nome}`);
    this.nome = nome; this.ate = this.agora() + DURACAO_MS;
  }
  atual() { return this.nome && this.agora() < this.ate ? this.nome : null; }
}

/** Liga o botão 😀 ao painel de gestos e anima o meu personagem. */
export function ligarEmotes(jogo, { botao, painel, balao }) {
  const g = (jogo.gestos = new Gestos());
  painel.replaceChildren(...Object.entries(EMOTES).map(([nome, emoji]) => el("button", {
    type: "button", className: "gesto", textContent: emoji, title: nome, ariaLabel: `Gesto ${nome}`,
    onclick: () => {
      g.fazer(nome);
      painel.hidden = true; botao.setAttribute("aria-expanded", "false");
      balao.textContent = emoji;
      balao.classList.remove("some"); void balao.offsetWidth; balao.classList.add("mostra");
      clearTimeout(balao._t); balao._t = setTimeout(() => balao.classList.replace("mostra", "some"), DURACAO_MS - 400);
      if (nome === "comemorar") {
        jogo.toque.pular = true; setTimeout(() => { jogo.toque.pular = false; }, 150);
        try { jogo.mundo.game.Efeitos.Confete(jogo.local.raiz.Position.add({ X: 0, Y: 4, Z: 0 })); } catch { /* sem efeitos */ }
      }
    },
  })));
  botao.addEventListener("click", () => {
    painel.hidden = !painel.hidden;
    botao.setAttribute("aria-expanded", String(!painel.hidden));
  });
  // 💃 dançar: gira o personagem (a rotação já vai para os outros pela rede)
  jogo.extras.push({
    quadro(dt) {
      if (g.atual() === "dancar" && jogo.local?.raiz) jogo.local.raiz._rotY = ((jogo.local.raiz._rotY || 0) + dt * 7) % (Math.PI * 2);
    },
  });
  return g;
}
