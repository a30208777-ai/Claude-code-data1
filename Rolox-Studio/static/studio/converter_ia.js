// VISTA — 🤖 converter .obj → .vista com IA. O .obj inteiro não cabe na IA, então mandamos um RESUMO:
// cada objeto/grupo (o / g) vira uma caixa (centro e tamanho) com o material (usemtl), já na escala do VISTA.
// A IA recebe isso + TODOS os documentos do VISTA e devolve as peças (bloco ```acoes```).

export const MAX_GRUPOS = 60;
export const TAMANHO_ALVO = 40;          // o modelo inteiro cabe em ~40 studs

export function resumoObj(texto, nome = "modelo") {
  const v = [], grupos = new Map();
  let atual = "corpo", mat = "";
  const g = () => {
    if (!grupos.has(atual)) grupos.set(atual, { nome: atual, mat, min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity], faces: 0 });
    return grupos.get(atual);
  };
  for (const linha of String(texto).split(/\r?\n/)) {
    const p = linha.trim().split(/\s+/);
    if (p[0] === "v" && p.length >= 4) v.push([+p[1], +p[2], +p[3]]);
    else if (p[0] === "o" || p[0] === "g") atual = (p.slice(1).join(" ") || "grupo").slice(0, 40);
    else if (p[0] === "usemtl") { mat = (p[1] || "").slice(0, 30); g().mat ||= mat; }
    else if (p[0] === "f") {
      const gr = g(); gr.faces++;
      for (const ref of p.slice(1)) {
        let i = parseInt(ref, 10); if (!i) continue;
        const pt = v[i > 0 ? i - 1 : v.length + i]; if (!pt) continue;
        for (let k = 0; k < 3; k++) { gr.min[k] = Math.min(gr.min[k], pt[k]); gr.max[k] = Math.max(gr.max[k], pt[k]); }
      }
    }
  }
  const lista = [...grupos.values()].filter((x) => x.faces && isFinite(x.min[0]));
  if (!lista.length) throw new Error("Esse .obj não tem faces (f). Exporte de novo com as faces.");
  const tot = { min: [0, 1, 2].map((k) => Math.min(...lista.map((x) => x.min[k]))), max: [0, 1, 2].map((k) => Math.max(...lista.map((x) => x.max[k]))) };
  const escala = TAMANHO_ALVO / Math.max(1e-6, ...[0, 1, 2].map((k) => tot.max[k] - tot.min[k]));
  const r = (n) => Math.round(n * 10) / 10;
  const meioX = (tot.min[0] + tot.max[0]) / 2, meioZ = (tot.min[2] + tot.max[2]) / 2;
  lista.sort((a, b) => b.faces - a.faces);
  const linhas = lista.slice(0, MAX_GRUPOS).map((x) => {
    const tam = [0, 1, 2].map((k) => r(Math.max(0.2, (x.max[k] - x.min[k]) * escala)));
    const c = [(x.min[0] + x.max[0]) / 2 - meioX, (x.min[1] + x.max[1]) / 2 - tot.min[1], (x.min[2] + x.max[2]) / 2 - meioZ].map((n) => r(n * escala));
    return `${x.nome} | centro [${c}] | tamanho [${tam}] | material "${x.mat}" | ${x.faces} faces`;
  });
  return {
    grupos: lista.length,
    texto: `Converta este modelo .obj "${nome}" para peças do VISTA (arquivo .vista).\n` +
      `${v.length} vértices, ${lista.length} grupos${lista.length > MAX_GRUPOS ? ` (mostrando os ${MAX_GRUPOS} maiores)` : ""}. ` +
      `Já está na escala do VISTA, com o chão em y=0.\n` + linhas.join("\n"),
  };
}

/** Nome do arquivo sem extensão (.vista, .rolox, .json, .obj). */
export function nomeSemExtensao(nome) {
  return String(nome || "").replace(/\.(vista|rolox|json|obj)$/i, "").replace(/[^\w-]/g, "_").slice(0, 40) || "modelo";
}
