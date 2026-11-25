// VISTA — 📸 foto do jogo: tira uma foto da cena (sem os botões por cima), põe a marca VISTA e o
// nome do jogo no canto e deixa salvar ou compartilhar. Nada sai do aparelho sem o jogador querer.

/** Nome de arquivo seguro: rolox-<jogo>-<data>.png */
export function nomeDaFoto(jogo, quando = new Date()) {
  const base = String(jogo || "jogo").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "jogo";
  const p = (n) => String(n).padStart(2, "0");
  return `rolox-${base}-${quando.getFullYear()}${p(quando.getMonth() + 1)}${p(quando.getDate())}-${p(quando.getHours())}${p(quando.getMinutes())}${p(quando.getSeconds())}.png`;
}

/** Desenha a cena agora e copia para um canvas 2D com a marca. Devolve o canvas. */
export function montarFoto(render, nomeJogo, documento = document) {
  render.desenhar();                                   // copiar logo depois de desenhar (o WebGL limpa depois)
  const origem = render.renderer.domElement;
  const c = documento.createElement("canvas");
  c.width = origem.width; c.height = origem.height;
  const g = c.getContext("2d");
  g.drawImage(origem, 0, 0);
  const t = Math.max(14, Math.round(c.height * 0.035));
  const texto = `VISTA · ${String(nomeJogo || "").slice(0, 40)}`;
  g.font = `800 ${t}px Inter, system-ui, sans-serif`;
  const larg = g.measureText(texto).width;
  const x = c.width - larg - t * 1.2, y = c.height - t * 0.9;
  g.fillStyle = "rgba(14, 10, 28, .55)";
  g.beginPath();
  g.roundRect?.(x - t * 0.5, y - t * 1.15, larg + t, t * 1.6, t * 0.4);
  g.fill();
  g.fillStyle = "#ffffff";
  g.fillText(texto, x, y);
  return c;
}

/** Tira a foto e oferece compartilhar (celular) ou baixar (PC). */
export async function tirarFoto(render, nomeJogo, { avisar = () => {} } = {}) {
  const canvas = montarFoto(render, nomeJogo);
  const blob = await new Promise((ok) => canvas.toBlob(ok, "image/png"));
  if (!blob) { avisar("Não deu para tirar a foto."); return null; }
  const nome = nomeDaFoto(nomeJogo);
  const arquivo = new File([blob], nome, { type: "image/png" });
  try {
    if (navigator.canShare?.({ files: [arquivo] })) {
      await navigator.share({ files: [arquivo], title: `VISTA · ${nomeJogo}` });
      return nome;
    }
  } catch (e) {
    if (e?.name === "AbortError") return null;         // o jogador cancelou
  }
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  avisar("📸 Foto salva!");
  return nome;
}

// ------------------------------------------------------------------ 🎥 clipe
/** Formato de vídeo que o navegador grava (webm na maioria, mp4 no Safari). */
export function formatoClipe(MR = globalThis.MediaRecorder) {
  for (const t of ["video/webm;codecs=vp9", "video/webm", "video/mp4"]) if (MR?.isTypeSupported?.(t)) return t;
  return null;
}

/** Grava N segundos da tela do jogo e baixa/compartilha o vídeo (o ROBLOX tirou o gravador; aqui tem). */
export async function gravarClipe(render, nomeJogo, { segundos = 10, avisar = () => {}, aoMudar = () => {} } = {}) {
  const tipo = formatoClipe();
  const tela = render.renderer.domElement;
  if (!tipo || !tela.captureStream) { avisar("Este aparelho não grava vídeo. Use o 📸."); return null; }
  const partes = [];
  const rec = new MediaRecorder(tela.captureStream(30), { mimeType: tipo, videoBitsPerSecond: 4_000_000 });
  rec.ondataavailable = (e) => e.data.size && partes.push(e.data);
  const fim = new Promise((ok) => { rec.onstop = ok; });
  rec.start(); aoMudar(true);
  setTimeout(() => rec.state !== "inactive" && rec.stop(), segundos * 1000);
  await fim; aoMudar(false);
  const ext = tipo.includes("mp4") ? "mp4" : "webm";
  const nome = nomeDaFoto(nomeJogo).replace(/\.png$/, "." + ext);
  const blob = new Blob(partes, { type: tipo.split(";")[0] });
  const arquivo = new File([blob], nome, { type: blob.type });
  try {
    if (navigator.canShare?.({ files: [arquivo] })) { await navigator.share({ files: [arquivo], title: `VISTA · ${nomeJogo}` }); return nome; }
  } catch (e) { if (e?.name === "AbortError") return null; }
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  avisar("🎥 Clipe salvo!");
  return nome;
}
