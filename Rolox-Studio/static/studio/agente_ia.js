// ROLOX Studio — a IA "põe a mão na massa".
//
// A IA responde com um bloco ```acoes [ ... ] ``` (JSON). Aqui ele é lido, conferido
// (só classes e propriedades permitidas, números com limite) e aplicado no mundo:
// criar peça/pasta/valor, criar script com o código, mudar propriedades, apagar.
// Apagar SEMPRE pede confirmação ao usuário (como no chat_ias.py). Tudo vira 1 passo
// do desfazer (↶), porque o editor fotografa o mundo depois.

import { Color3, Vector3, criar, materialValido } from "./motor.js";

export const MAX_ACOES = 60;
const LIMITE = 2000;                                       // coordenadas/tamanhos
const CLASSES_PECA = new Set(["Part", "SpawnLocation", "Checkpoint"]);
const CLASSES_OUTRAS = new Set(["Model", "Folder", "IntValue", "NumberValue"]);
const CLASSES_SCRIPT = new Set(["Script", "LocalScript", "ModuleScript"]);
const FORMAS = new Set(["Block", "Ball", "Cylinder"]);
const NOME = /^[^.\n\r]{1,40}$/;

const APELIDOS = {
  workspace: "Workspace", serverscriptservice: "ServerScriptService", replicatedstorage: "ReplicatedStorage",
  starterplayerscripts: "StarterPlayer.StarterPlayerScripts", starterplayer: "StarterPlayer",
};

/** Separa o bloco ```acoes``` do texto. Devolve { acoes, texto, erro }. */
export function extrairAcoes(resposta) {
  const re = /```acoes\s*\n?([\s\S]*?)```/gi;
  let acoes = [], erro = null, m;
  while ((m = re.exec(resposta))) {
    try {
      const v = JSON.parse(m[1]);
      acoes = acoes.concat(Array.isArray(v) ? v : [v]);
    } catch { erro = "A IA mandou ações com erro de formato (nada foi feito com elas)."; }
  }
  return { acoes: acoes.slice(0, MAX_ACOES), texto: resposta.replace(re, "").trim(), erro };
}

function num(v, padrao = 0, lim = LIMITE) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(-lim, Math.min(lim, n)) : padrao;
}
function vetor(v, padrao) {
  return Array.isArray(v) && v.length === 3 ? new Vector3(num(v[0]), num(v[1]), num(v[2])) : padrao;
}
function cor(v) {
  if (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v)) return Color3.fromHex(v);
  if (Array.isArray(v) && v.length === 3) return Color3.fromRGB(num(v[0], 0, 255), num(v[1], 0, 255), num(v[2], 0, 255));
  return null;
}

/** "Workspace.Porta" ou "StarterPlayerScripts" -> instância (ou null). */
export function acharCaminho(mundo, caminho) {
  if (typeof caminho !== "string" || !caminho.trim()) return null;
  const partes = caminho.trim().replace(/^game\./i, "").split(".");
  const primeiro = APELIDOS[partes[0].toLowerCase()];
  const nomes = primeiro ? [...primeiro.split("."), ...partes.slice(1)] : partes;
  let atual = mundo.game;
  for (const n of nomes) { atual = atual?.FindFirstChild(n); if (!atual) return null; }
  return atual;
}

function paiPadrao(mundo, classe) {
  const g = mundo.game;
  if (classe === "Script") return g.ServerScriptService;
  if (classe === "LocalScript") return g.StarterPlayer.FindFirstChildOfClass("StarterPlayerScripts");
  if (classe === "ModuleScript") return g.ReplicatedStorage;
  return mundo.workspace;
}

/** Aplica propriedades permitidas. Devolve a lista do que mudou. */
export function aplicarPropriedades(i, p = {}) {
  const feito = [];
  if (typeof p.nome === "string" && NOME.test(p.nome)) { i.Name = p.nome; feito.push("nome"); }
  if ("Position" in i) {
    const pos = vetor(p.posicao, null); if (pos) { i.Position = pos; feito.push("posição"); }
    const tam = vetor(p.tamanho, null);
    if (tam) { i.Size = new Vector3(Math.max(0.1, Math.abs(tam.X)), Math.max(0.1, Math.abs(tam.Y)), Math.max(0.1, Math.abs(tam.Z))); feito.push("tamanho"); }
    const rot = vetor(p.rotacao, null); if (rot) { i.Rotation = rot; feito.push("rotação"); }
    const c = cor(p.cor); if (c) { i.Color = c; feito.push("cor"); }
    if (typeof p.ancorada === "boolean") { i.Anchored = p.ancorada; feito.push("ancorada"); }
    if (typeof p.colide === "boolean") { i.CanCollide = p.colide; feito.push("colisão"); }
    if (p.transparencia !== undefined) { i.Transparency = num(p.transparencia, 0, 1); feito.push("transparência"); }
    if (FORMAS.has(p.forma)) { i.Shape = p.forma; feito.push("forma"); }
    if (p.material !== undefined && materialValido(p.material)) { i.Material = p.material; feito.push("material"); }
  }
  if ("Value" in i && p.valor !== undefined) { i.Value = num(p.valor, 0, 1e12); feito.push("valor"); }
  if (typeof i.definirLinguagem === "function") {
    if (typeof p.codigo === "string") {
      const lang = p.linguagem === "python" || p.linguagem === "lua" ? p.linguagem : i.Linguagem;
      i.Source = `_++linguagemprogroma++_ = ${lang}\n` + p.codigo.slice(0, 20000).replace(/^\s*(?:--|#)?\s*_\+\+linguagemprogroma\+\+_.*\n/i, "");
      i._mudou?.("Source");
      feito.push("código");
    } else if (p.linguagem === "python" || p.linguagem === "lua") { i.definirLinguagem(p.linguagem); feito.push("linguagem"); }
  }
  return feito;
}

/**
 * Executa as ações. `confirmar(texto)` -> Promise<boolean> (para apagar).
 * Devolve { log: [...], criados: [...] }.
 */
export async function aplicarAcoes(mundo, acoes, { confirmar = async () => false, limitePartes = 400 } = {}) {
  const log = [], criados = [];
  for (const a of Array.isArray(acoes) ? acoes : []) {
    try {
      if (!a || typeof a !== "object") continue;
      const tipo = String(a.acao || "").toLowerCase();
      if (tipo === "criar") {
        const classe = String(a.classe || "Part");
        if (!CLASSES_PECA.has(classe) && !CLASSES_OUTRAS.has(classe) && !CLASSES_SCRIPT.has(classe)) {
          log.push(`❌ classe não permitida: ${classe}`); continue;
        }
        const pai = (a.pai && acharCaminho(mundo, a.pai)) || paiPadrao(mundo, classe);
        const nome = typeof a.nome === "string" && NOME.test(a.nome) ? a.nome : classe;
        // já existe com esse nome nesse lugar? atualiza em vez de duplicar
        const existente = pai.FindFirstChild(nome);
        if (existente && existente.ClassName === classe) {
          const f = aplicarPropriedades(existente, { ...a, nome: undefined });
          log.push(`✏️ ${existente.GetFullName()} já existia — atualizei (${f.join(", ") || "nada"})`);
          criados.push(existente);
          continue;
        }
        if (CLASSES_PECA.has(classe) && mundo.contarPartes() >= limitePartes) { log.push(`❌ limite de ${limitePartes} peças`); continue; }
        const i = criar(classe);
        if (CLASSES_PECA.has(classe)) i.Anchored = true;          // padrão: não cai
        aplicarPropriedades(i, { ...a, nome });
        i.Parent = pai;
        criados.push(i);
        log.push(`✅ criei ${classe} ${i.GetFullName()}`);
      } else if (tipo === "editar") {
        const i = acharCaminho(mundo, a.alvo);
        if (!i) { log.push(`❌ não achei ${a.alvo}`); continue; }
        if (i.constructor.naoCriavel) { log.push(`❌ ${a.alvo} não pode ser editado`); continue; }
        const f = aplicarPropriedades(i, a);
        log.push(`✏️ ${i.GetFullName()}: ${f.join(", ") || "nada mudou"}`);
      } else if (tipo === "apagar") {
        const i = acharCaminho(mundo, a.alvo);
        if (!i || i.constructor.naoCriavel || i === mundo.workspace) { log.push(`❌ não dá para apagar ${a.alvo}`); continue; }
        if (await confirmar(`A IA quer apagar "${i.GetFullName()}". Permitir?`)) { const n = i.GetFullName(); i.Destroy(); log.push(`🗑️ apaguei ${n}`); }
        else log.push(`🚫 não apaguei ${i.GetFullName()} (você não permitiu)`);
      } else if (tipo === "ceu") {
        const c = mundo.game.Ceu;
        if (a.hora !== undefined) c.Hora = num(a.hora, 0, 24);
        if (a.neblina !== undefined) c.Neblina = num(a.neblina, 0, 1);
        if (typeof a.estrelas === "boolean") c.Estrelas = a.estrelas;
        log.push(`🌤️ céu: ${c.Hora}h, neblina ${c.Neblina}`);
      } else {
        log.push(`❌ ação desconhecida: ${tipo || "(vazia)"}`);
      }
    } catch (e) { log.push(`❌ erro: ${e.message}`); }
  }
  return { log, criados };
}

/** Resumo do mapa para a IA saber o que já existe (o que não tem não é inventado). */
export function resumoCena(mundo, maxLinhas = 120) {
  const linhas = [];
  const f = (v) => `(${[v.X, v.Y, v.Z].map((n) => Math.round(n * 10) / 10).join(", ")})`;
  const visitar = (i, nivel) => {
    if (linhas.length >= maxLinhas || i._temporaria) return;
    let d = `${"  ".repeat(nivel)}${i.Name} [${i.ClassName}]`;
    if ("Position" in i && i.Size) d += ` pos=${f(i.Position)} tam=${f(i.Size)}${i.Anchored ? "" : " solta"}${i.CanCollide ? "" : " sem-colisão"}${i.Material && i.Material !== "Plastico" ? ` ${i.Material}` : ""}`;
    if (typeof i.definirLinguagem === "function") d += ` ${i.Linguagem}, ${String(i.Source).split("\n").length} linhas`;
    if ("Value" in i) d += ` valor=${i.Value}`;
    linhas.push(d);
    for (const c of i.GetChildren()) visitar(c, nivel + 1);
  };
  for (const s of ["Workspace", "ServerScriptService", "ReplicatedStorage", "StarterPlayer"]) {
    const x = mundo.game.FindFirstChild(s); if (x) visitar(x, 0);
  }
  const c = mundo.game.FindFirstChild("Ceu");
  if (c && (c.Hora !== 12 || c.Neblina)) linhas.push(`Ceu: hora ${c.Hora}, neblina ${c.Neblina}`);
  if (linhas.length >= maxLinhas) linhas.push("... (mapa grande, resumo cortado)");
  return linhas.join("\n");
}
