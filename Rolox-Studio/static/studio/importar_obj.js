// Vista Studio — importar .obj (por exemplo, exportado pelo Roblox Studio com
// "Export Selection", que gera .obj + .mtl + texturas .png).
// Selecione os arquivos juntos; vira um MeshPart no Workspace.

import { criar, Vector3 } from "./motor.js";

const MAX_TEXTURA = 4 * 1024 * 1024;     // por imagem
const MAX_OBJ = 30 * 1024 * 1024;

const lerTexto = (f) => f.text();
const lerDataUrl = (f) => new Promise((ok, erro) => {
  const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => erro(r.error); r.readAsDataURL(f);
});

/** Lê os arquivos escolhidos e devolve {asset, nome, avisos}. */
export async function lerArquivosObj(arquivos) {
  const lista = [...arquivos];
  const obj = lista.find((f) => /\.obj$/i.test(f.name));
  if (!obj) throw new Error("Escolha um arquivo .obj (pode escolher junto o .mtl e as texturas).");
  if (obj.size > MAX_OBJ) throw new Error("O .obj passa de 30 MB. Reduza a malha antes de importar.");
  const avisos = [];
  const mtl = lista.find((f) => /\.mtl$/i.test(f.name));
  const asset = { nome: obj.name, obj: await lerTexto(obj), mtl: mtl ? await lerTexto(mtl) : "", texturas: {} };
  for (const img of lista.filter((f) => /\.(png|jpe?g|webp)$/i.test(f.name))) {
    if (img.size > MAX_TEXTURA) { avisos.push(`${img.name}: maior que 4 MB, ignorada`); continue; }
    asset.texturas[img.name] = await lerDataUrl(img);
  }
  if (mtl) {
    const pedidas = [...asset.mtl.matchAll(/^\s*map_\w+\s+(.+)$/gim)].map((m) => m[1].trim().split(/[\\/]/).pop());
    const faltando = pedidas.filter((n) => !Object.keys(asset.texturas).some((t) => t.toLowerCase() === n.toLowerCase()));
    if (faltando.length) avisos.push(`Texturas não enviadas: ${[...new Set(faltando)].join(", ")}`);
  } else {
    avisos.push("Sem .mtl: a malha fica com a cor da peça.");
  }
  return { asset, nome: obj.name.replace(/\.obj$/i, ""), avisos };
}

/** Coloca o asset no mundo e cria o MeshPart (tamanho = tamanho real da malha). */
export async function importarNoMundo(mundo, render, arquivos, posicao) {
  const { asset, nome, avisos } = await lerArquivosObj(arquivos);
  const id = `malha_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  mundo.assets[id] = asset;
  const malha = await render.carregarMalha(id);
  const t = malha.userData.tamanho;
  const p = criar("MeshPart");
  p.Name = nome.slice(0, 40) || "Malha";
  p.MeshId = id;
  p.Size = new Vector3(t.x || 1, t.y || 1, t.z || 1);
  p.Position = (posicao || new Vector3()).add(new Vector3(0, (t.y || 1) / 2, 0));
  p.Parent = mundo.workspace;
  return { parte: p, avisos };
}
