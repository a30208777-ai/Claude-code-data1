// ROLOX — jogar um mapa publicado (página /jogar do site).
// Carrega o mapa do bucket (via site), cria o personagem e roda scripts + física,
// com a câmera do jogador (camera.js), teclado e joystick de toque.

import { carregarMundo } from "./motor.js";
import { Render } from "./render.js";
import { Jogo } from "./jogo.js";
import { MundoRede } from "./mundo_rede.js";
import { ligarTela, ligarSons } from "./tela_jogo.js";

const ehToque = () => matchMedia("(pointer: coarse)").matches || "ontouchstart" in window;

export async function jogarMapa({ canvas, urlMapa, nomeJogador = "Jogador", avatar = {}, saida = () => {}, aoCarregar = () => {},
                                  multijogador = false, cofre = null }) {
  const r = await fetch(urlMapa, { cache: "no-store" });
  if (!r.ok) throw new Error(r.status === 404 ? "mapa não encontrado" : `não deu para baixar o mapa (${r.status})`);
  const mundo = carregarMundo(await r.json());
  const modo = ehToque() ? "leve" : "pesado";
  const render = new Render(canvas, mundo, modo);
  render.grade.visible = false;                       // no jogo publicado não tem grade do editor
  // multijogador: começa como convidado; o site diz em seguida quem é o anfitrião (quem roda os Scripts)
  const jogo = new Jogo({ mundoEditor: mundo, render, saida, nomeJogador, avatar, rodarServidor: !multijogador });
  const mundoRede = new MundoRede(jogo.mundo);
  mundoRede.indexar();                 // antes de criar personagens e rodar scripts
  mundoRede.ligar();
  if (multijogador) mundoRede.modoConvidado();      // sozinho: não precisa espelhar nada
  jogo.mundoRede = mundoRede;
  ligarTela(jogo, document.body);        // antes dos scripts: o que eles mostram logo no começo aparece
  ligarSons(jogo);
  // Cofre: dados salvos do jogador neste jogo (carrega ANTES dos scripts rodarem)
  if (cofre?.url) {
    try {
      const rc = await fetch(cofre.url, { cache: "no-store" });
      if (rc.ok) jogo.mundo.game.Cofre._carregar(await rc.json());
    } catch { /* sem rede: começa vazio, salva depois */ }
    const enviar = (keepalive = false) => {
      const dados = jogo.mundo.game.Cofre._pendentes();
      if (!dados) return;
      fetch(cofre.url, { method: "POST", keepalive, headers: { "Content-Type": "application/json", "X-CSRF": cofre.csrf },
                         body: JSON.stringify({ dados }) })
        .then((r) => { if (r.ok) jogo.mundo.game.Cofre.Salvo.Fire(); else saida("Cofre: não deu para salvar", "erro"); })
        .catch(() => { for (const [k, v] of Object.entries(dados)) jogo.mundo.game.Cofre._sujos.add(k); });
    };
    setInterval(enviar, 3000);
    addEventListener("pagehide", () => enviar(true));
  }
  jogo.render = render;
  jogo.extras = [];          // ex.: multijogador (quadro(dt) antes da física, nomes() depois de desenhar)
  await jogo.iniciar();
  aoCarregar(jogo);

  // teclado (ignora quando está digitando no chat)
  const digitando = () => ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  addEventListener("keydown", (e) => {
    if (digitando()) return;
    jogo.teclas.add(e.key.toLowerCase());
    if (e.key === " ") e.preventDefault();
  });
  addEventListener("keyup", (e) => jogo.teclas.delete(e.key.toLowerCase()));
  addEventListener("blur", () => jogo.teclas.clear());

  let antes = performance.now();
  function loop() {
    if (!jogo.rodando) return;
    const agora = performance.now(), dt = Math.min(0.1, (agora - antes) / 1000);
    antes = agora;
    for (const x of jogo.extras) x.quadro?.(dt);
    jogo.passo();
    render.desenhar();
    for (const x of jogo.extras) x.nomes?.();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
  return jogo;
}

/** Liga o joystick (#joystick/#manche) e o botão de pular (#botaoPulo) ao jogo. */
export function ligarToque(jogo, { base, manche, pulo }) {
  let id = null;
  const mover = (e) => {
    const r = base.getBoundingClientRect();
    let dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2), dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    const m = Math.hypot(dx, dy); if (m > 1) { dx /= m; dy /= m; }
    manche.style.transform = `translate(${dx * 40}px, ${dy * 40}px)`;
    jogo.toque.x = dx; jogo.toque.z = -dy;
  };
  base.addEventListener("pointerdown", (e) => { id = e.pointerId; base.setPointerCapture(id); mover(e); });
  base.addEventListener("pointermove", (e) => { if (e.pointerId === id) mover(e); });
  const soltar = () => { id = null; manche.style.transform = ""; jogo.toque.x = 0; jogo.toque.z = 0; };
  base.addEventListener("pointerup", soltar); base.addEventListener("pointercancel", soltar);
  pulo.addEventListener("pointerdown", () => { jogo.toque.pular = true; });
  const parar = () => { jogo.toque.pular = false; };
  pulo.addEventListener("pointerup", parar); pulo.addEventListener("pointercancel", parar);
}
