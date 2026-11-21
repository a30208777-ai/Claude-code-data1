// ROLOX — painel do dono 👑💎 dentro do jogo (só aparece para o dono; o site e o banco conferem de novo).
//   Jogadores: 📍 ir até · 👢 expulsar (kick) · 🔨 banir (o dono nunca pode ser banido)
//   Poderes:   voar, velocidade, super pulo, vida infinita, gravidade, spawn, explosão, festa, voltar ao normal
//   📢 Anúncio para todo mundo do servidor · 🤖 executor de scripts em qualquer servidor

import { Vector3 } from "./motor.js";
import { SCRIPTS_PRONTOS } from "./executor.js";

const PODERES = {
  "✈️ Voar": SCRIPTS_PRONTOS["✈️ Voar"],
  "⚡ Velocidade": SCRIPTS_PRONTOS["⚡ Velocidade x3"],
  "🦘 Super pulo": SCRIPTS_PRONTOS["🦘 Super pulo"],
  "❤️ Vida infinita": SCRIPTS_PRONTOS["❤️ Vida infinita"],
  "🌙 Gravidade baixa": SCRIPTS_PRONTOS["🌙 Gravidade da lua"],
  "🏠 Ir ao spawn": SCRIPTS_PRONTOS["🏠 Voltar ao spawn"],
  "💥 Explosão": SCRIPTS_PRONTOS["💥 Explosão na frente"],
  "🎉 Festa": SCRIPTS_PRONTOS["🎉 Festa"],
  "🔄 Normal": `local h = game.Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
h.WalkSpeed = 16
h.JumpPower = 50
workspace.Gravity = 196.2
print("Tudo normal de novo")`,
};

const el = (tag, props = {}, ...filhos) => { const e = Object.assign(document.createElement(tag), props); e.append(...filhos); return e; };

/**
 * @param jogo      o jogo rodando
 * @param botao     botão 👑💎 (abre/fecha)
 * @param painel    elemento do painel
 * @param mj        Multijogador (ou null jogando sozinho/teste)
 * @param executor  { rodar(codigo) } do executor.js
 * @param abrirExecutor  () => void  (mostra o executor 🤖)
 * @param passe, csrf    para falar com o site
 */
export function ligarPainelDono({ jogo, botao, painel, mj = null, executor, abrirExecutor, passe = null, csrf = "",
                                  url = "/api/dono/jogo" }) {
  const aviso = (texto) => { try { jogo.mundo.game.Tela.Aviso(texto, 3); } catch { /* sem tela */ } };
  const pedir = async (acao, corpo) => {
    const r = await fetch(`${url}/${acao}`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
                                               body: JSON.stringify({ passe, ...corpo }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.mensagem || `erro ${r.status}`);
    return d;
  };

  const lista = el("div", { className: "dono-jogadores" });
  const motivo = el("input", { type: "text", maxLength: 200, placeholder: "Motivo do kick/ban (opcional)", className: "dono-texto" });
  motivo.addEventListener("keydown", (e) => e.stopPropagation());
  const titulo = el("div", { className: "dono-sub" });
  const poderes = el("div", { className: "dono-poderes" },
    ...Object.entries(PODERES).map(([nome, codigo]) => el("button", {
      type: "button", className: "dono-poder", textContent: nome,
      onclick: () => { if (executor.rodar(codigo)) aviso(`👑 ${nome}`); },
    })),
    el("button", { type: "button", className: "dono-poder", textContent: "🤖 Executor", onclick: () => abrirExecutor() }));
  const texto = el("input", { type: "text", maxLength: 200, placeholder: "Mensagem para todo mundo do servidor", className: "dono-texto" });
  const anunciar = el("button", { type: "button", className: "btn pequeno", textContent: "📢 Anunciar" });
  const fechar = el("button", { type: "button", className: "btn-jogo pequeno", textContent: "✕", ariaLabel: "Fechar painel do dono" });
  painel.replaceChildren(
    el("div", { className: "exec-topo" }, el("b", { textContent: "👑💎 Painel do dono" }), el("span", { className: "exec-nota", textContent: "só você vê" }), fechar),
    titulo, motivo, lista,
    el("div", { className: "dono-sub", textContent: "Poderes" }), poderes,
    el("div", { className: "dono-sub", textContent: "Anúncio" }), el("div", { className: "exec-botoes" }, texto, anunciar));

  texto.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Enter") anunciar.click(); });
  anunciar.addEventListener("click", async () => {
    const t = texto.value.trim();
    if (!t) return;
    if (!passe) { aviso(`👑 ${t}`); return; }           // jogando sozinho: só aparece para você
    try { const d = await pedir("anunciar", { texto: t }); texto.value = ""; aviso(`📢 Enviado para ${d.viram} jogador(es)`); }
    catch (e) { aviso(`❌ ${e.message}`); }
  });

  const desenhar = () => {
    const outros = mj ? [...mj.outros.values()] : [];
    titulo.textContent = `Jogadores no servidor (${outros.length})`;
    if (!outros.length) {
      lista.replaceChildren(el("p", { className: "exec-nota", textContent: passe ? "Só você está aqui agora." : "Jogando sozinho (sem servidor): kick e ban só num servidor." }));
      return;
    }
    lista.replaceChildren(...outros.map((o) => el("div", { className: "dono-jogador" },
      el("span", { className: "dono-nome", textContent: (o.dn ? "👑 " : "") + o.n }),
      el("button", { type: "button", className: "dono-acao", textContent: "📍", title: "Ir até", onclick: () => {
        const raiz = jogo.local?.raiz;
        if (raiz) { raiz.Position = o.raiz.Position.add(new Vector3(3, 2, 0)); raiz.Velocity = new Vector3(); }
      } }),
      ...(o.dn ? [] : [
        el("button", { type: "button", className: "dono-acao", textContent: "👢 Kick", onclick: async () => {
          try { await pedir("expulsar", { alvo: o.id, motivo: motivo.value.trim() }); aviso(`👢 ${o.n} foi expulso`); motivo.value = ""; }
          catch (e) { aviso(`❌ ${e.message}`); }
        } }),
        el("button", { type: "button", className: "dono-acao perigo", textContent: "🔨 Ban", onclick: async (ev) => {
          const b = ev.currentTarget;
          if (b.dataset.certeza !== "1") {                // 2 toques: banir não tem volta pelo jogo
            b.dataset.certeza = "1"; b.textContent = "Certeza?";
            setTimeout(() => { b.dataset.certeza = ""; b.textContent = "🔨 Ban"; }, 4000);
            return;
          }
          try { await pedir("banir", { alvo: o.id, motivo: motivo.value.trim() }); aviso(`🔨 ${o.n} foi banido`); motivo.value = ""; }
          catch (e) { aviso(`❌ ${e.message}`); }
        } }),
      ]))));
  };

  let timer = null;
  const abrir = (sim) => {
    painel.hidden = !sim;
    botao.setAttribute("aria-expanded", String(sim));
    clearInterval(timer);
    if (sim) { desenhar(); timer = setInterval(desenhar, 2000); }
  };
  botao.addEventListener("click", () => abrir(painel.hidden));
  fechar.addEventListener("click", () => abrir(false));
  return { abrir, desenhar };
}
