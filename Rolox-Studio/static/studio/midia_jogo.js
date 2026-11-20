// ROLOX — toca os Sons (Som) e os vídeos (TelaVideo) dos criadores durante o jogo.
// Os arquivos vêm do bucket público "midias" do Supabase (base em window.ROLOX_MIDIAS).
import * as THREE from "three";
import { MIDIA } from "./motor.js";

export function urlMidia(midia, base = window.ROLOX_MIDIAS || "") {
  return base && MIDIA.test(String(midia || "")) ? `${base.replace(/\/$/, "")}/${midia}` : "";
}

export function ligarMidias(jogo, render) {
  const tocadores = new Map();          // instância -> <audio>/<video>
  const ehMidia = (i) => i.ClassName === "Som" || i.ClassName === "TelaVideo";

  function tocador(i) {
    let el = tocadores.get(i);
    const url = urlMidia(i.Midia);
    if (!url) return null;
    if (!el) {
      el = document.createElement(i.ClassName === "Som" ? "audio" : "video");
      el.crossOrigin = "anonymous"; el.preload = "auto"; el.playsInline = true; el.src = url;
      tocadores.set(i, el);
      if (i.ClassName === "TelaVideo") {
        const tex = new THREE.VideoTexture(el);
        tex.colorSpace = THREE.SRGBColorSpace;
        const o = render.objetoDe(i);
        if (o?.material) { o.material = new THREE.MeshBasicMaterial({ map: tex }); }
      }
    }
    el.loop = !!i.Repetir;
    if (i.ClassName === "Som") el.volume = i.Volume; else el.muted = !i.ComSom;
    return el;
  }

  function aplicar(i) {
    const el = tocador(i);
    if (!el) return;
    if (i.Tocando) el.play().catch(() => { /* navegador pede um toque antes de tocar som */ });
    else el.pause();
  }

  jogo.mundo.on("mudou", (i, prop) => {
    if (!jogo.rodando || !ehMidia(i)) return;
    if (prop === "Tocando" || prop === "Volume" || prop === "Midia") aplicar(i);
  });
  // quem começa tocando
  for (const i of jogo.mundo.game.GetDescendants()) {
    if (ehMidia(i) && i.TocarAoComecar) i.Tocar();
  }
  return () => { for (const el of tocadores.values()) { el.pause(); el.removeAttribute("src"); el.load?.(); } tocadores.clear(); };
}
