// VISTA Studio — 📋 copiar e colar (também entre projetos: a cópia fica guardada neste aparelho).

import { BasePart, Vector3, salvarInstancia, carregarInstancia } from "./motor.js";

const CHAVE = "rolox.studio.copiado";
const MAX = 512 * 1024;           // 512 KB de cópia, no máximo

/** Guarda a instância (com filhos e scripts). Devolve quantas instâncias foram copiadas. */
export function copiar(inst, arm = globalThis.localStorage) {
  if (!inst || inst.constructor.naoCriavel) throw new Error("Selecione uma peça, modelo, pasta ou script para copiar.");
  const dados = JSON.stringify({ formato: "rolox-copia", versao: 1, item: salvarInstancia(inst) });
  if (dados.length > MAX) throw new Error("Grande demais para copiar (máx. 512 KB).");
  arm.setItem(CHAVE, dados);
  return 1 + inst.GetDescendants().length;
}

export function temCopia(arm = globalThis.localStorage) {
  try { return !!arm.getItem(CHAVE); } catch { return false; }
}

/** Cria a cópia dentro de `pai`, um pouco ao lado do original. Devolve a instância nova. */
export function colar(pai, arm = globalThis.localStorage, deslocar = new Vector3(4, 0, 4)) {
  let d;
  try { d = JSON.parse(arm.getItem(CHAVE) || "null"); } catch { d = null; }
  if (!d || d.formato !== "rolox-copia" || !d.item) throw new Error("Nada copiado ainda (use Copiar ou Ctrl+C).");
  const novo = carregarInstancia(d.item, null);
  const pecas = novo instanceof BasePart ? [novo] : [];
  pecas.push(...novo.GetDescendants().filter((x) => x instanceof BasePart));
  for (const p of pecas) p.Position = p.Position.add(deslocar);
  novo.Parent = pai;
  return novo;
}
