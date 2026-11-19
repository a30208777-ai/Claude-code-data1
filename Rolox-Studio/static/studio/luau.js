// Rolox Studio — tradutor de Luau para Lua 5.3 (o Fengari roda Lua 5.3).
//
// Suporta o que mais aparece em scripts Luau:
//   local x: number = 1            -> local x = 1          (tipos em locais, parâmetros, retornos, for)
//   function f<T>(a: T): T          -> function f(a)
//   type Ponto = {x: number}        -> (removido)            (também "export type")
//   valor :: number                 -> valor                 (asserção de tipo)
//   x += 1   (-= *= /= //= %= ^= ..=)
//   `Olá {nome}!`                   -> ("Olá " .. __texto(nome) .. "!")
//   continue                        -> goto + rótulo no fim do laço
// Mantém as quebras de linha, então os erros apontam a linha certa do script.

const PALAVRAS = new Set(("and break do else elseif end false for function goto if in local nil not or " +
  "repeat return then true until while").split(" "));
const OPERADORES = ["...", "..=", "//=", "::", "..", "==", "~=", "<=", ">=", "//", "->", "+=", "-=", "*=", "/=", "%=", "^=",
  "<<", ">>", "+", "-", "*", "/", "%", "^", "#", "&", "~", "|", "<", ">", "=", "(", ")", "{", "}", "[", "]", ";", ":", ",", ".", "?"];

export function tokenizar(src) {
  const t = [];
  let i = 0;
  const n = src.length;
  const longo = (pos) => {          // [[ ... ]] ou [==[ ... ]==]
    const m = /^\[(=*)\[/.exec(src.slice(pos, pos + 64));
    if (!m) return -1;
    const fim = src.indexOf(`]${m[1]}]`, pos + m[0].length);
    return fim < 0 ? n : fim + m[1].length + 2;
  };
  while (i < n) {
    const c = src[i];
    if (/\s/.test(c)) {
      let j = i; while (j < n && /\s/.test(src[j])) j++;
      t.push({ tipo: "espaco", v: src.slice(i, j) }); i = j; continue;
    }
    if (c === "-" && src[i + 1] === "-") {
      let j = longo(i + 2);
      if (j < 0) { j = src.indexOf("\n", i); if (j < 0) j = n; }
      t.push({ tipo: "comentario", v: src.slice(i, j) }); i = j; continue;
    }
    if (c === "[" && (src[i + 1] === "[" || src[i + 1] === "=")) {
      const j = longo(i);
      if (j > 0) { t.push({ tipo: "texto", v: src.slice(i, j) }); i = j; continue; }
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && src[j] !== c && src[j] !== "\n") j += src[j] === "\\" ? 2 : 1;
      t.push({ tipo: "texto", v: src.slice(i, j + 1) }); i = j + 1; continue;
    }
    if (c === "`") {
      let j = i + 1, prof = 0;
      while (j < n) {
        if (src[j] === "\\") { j += 2; continue; }
        if (prof === 0 && src[j] === "`") break;
        if (src[j] === "{") prof++; else if (src[j] === "}" && prof > 0) prof--;
        j++;
      }
      t.push({ tipo: "crase", v: src.slice(i, j + 1) }); i = j + 1; continue;
    }
    if (/[0-9]/.test(c) || (c === "." && /[0-9]/.test(src[i + 1] || ""))) {
      const m = /^(0[xX][0-9a-fA-F_]+|0[bB][01_]+|[0-9_]*\.?[0-9_]+(?:[eE][+-]?[0-9]+)?)/.exec(src.slice(i));
      const v = m ? m[0] : c;
      t.push({ tipo: "numero", v: v.replace(/_/g, "").replace(/^0[bB]([01]+)$/, (_, b) => String(parseInt(b, 2))) });
      i += v.length; continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      let j = i; while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      const v = src.slice(i, j);
      t.push({ tipo: PALAVRAS.has(v) ? "palavra" : "nome", v }); i = j; continue;
    }
    const op = OPERADORES.find((o) => src.startsWith(o, i));
    t.push({ tipo: "op", v: op || c }); i += (op || c).length;
  }
  return t;
}

const significativo = (tk) => tk && tk.tipo !== "espaco" && tk.tipo !== "comentario";
const quebras = (s) => (s.match(/\n/g) || []).join("");

class Leitor {
  constructor(tokens) { this.t = tokens; }
  prox(i) { let j = i + 1; while (j < this.t.length && !significativo(this.t[j])) j++; return j; }
  ant(i) { let j = i - 1; while (j >= 0 && !significativo(this.t[j])) j--; return j; }
  eh(i, v) { return this.t[i] && significativo(this.t[i]) && this.t[i].v === v; }
  /** Pula uma expressão de tipo começando em i; devolve o índice depois dela. */
  pularTipo(i) {
    const t = this.t;
    const simples = (k) => {
      const tk = t[k];
      if (!tk) return k;
      if (tk.v === "(" || tk.v === "{") {
        k = this.fecharGrupo(k);
        const d = this.prox(k - 1);
        if (this.eh(d, "->")) return this.pularTipo(this.prox(d));
        return k;
      }
      if (tk.v === "typeof" && this.eh(this.prox(k), "(")) return this.fecharGrupo(this.prox(k));
      if (tk.tipo === "nome" || tk.v === "nil" || tk.tipo === "texto" || tk.v === "true" || tk.v === "false" || tk.v === "...") {
        k = this.prox(k);
        while (this.eh(k, ".") && t[this.prox(k)]?.tipo === "nome") k = this.prox(this.prox(k));
        if (this.eh(k, "<")) k = this.fecharAngulo(k);
        return this.ant(k) + 1;
      }
      return k + 1;
    };
    let k = simples(this.prox(i - 1));
    for (;;) {
      const d = this.prox(k - 1);
      if (this.eh(d, "?")) { k = d + 1; continue; }
      if (this.eh(d, "|") || this.eh(d, "&")) { k = simples(this.prox(d)); continue; }
      return k;
    }
  }
  fecharGrupo(k) {              // ( { [  ->  índice depois do fechamento
    const abre = this.t[k].v, fecha = { "(": ")", "{": "}", "[": "]" }[abre];
    let prof = 0;
    for (let j = k; j < this.t.length; j++) {
      if (!significativo(this.t[j])) continue;
      if (this.t[j].v === abre) prof++;
      else if (this.t[j].v === fecha && --prof === 0) return j + 1;
    }
    return this.t.length;
  }
  fecharAngulo(k) {
    let prof = 0;
    for (let j = k; j < this.t.length; j++) {
      const v = this.t[j].v;
      if (!significativo(this.t[j])) continue;
      if (v === "<") prof++;
      else if (v === ">" && --prof === 0) return j + 1;
      else if (v === ">>") { prof -= 2; if (prof <= 0) return j + 1; }
      else if (v === "(" || v === "{") { j = this.fecharGrupo(j) - 1; }
    }
    return this.t.length;
  }
}

/** Troca t[a..b) por um texto, mantendo as quebras de linha. */
function apagar(t, a, b, novo = "") {
  let nl = "";
  for (let k = a; k < b; k++) nl += quebras(t[k].v);
  for (let k = a; k < b; k++) t[k] = { tipo: "espaco", v: "" };
  t[a] = { tipo: novo ? "op" : "espaco", v: novo + (nl || (novo ? "" : " ")) };
}

function tirarTipos(t) {
  const L = new Leitor(t);
  let pendenteFuncao = false;
  for (let i = 0; i < t.length; i++) {
    const tk = t[i];
    if (!significativo(tk)) continue;
    // type X = ... / export type X = ...
    if (tk.tipo === "nome" && (tk.v === "type" || tk.v === "export")) {
      let k = i;
      if (tk.v === "export") { k = L.prox(i); if (t[k]?.v !== "type") continue; }
      const nome = L.prox(k);
      if (t[nome]?.tipo !== "nome") continue;
      let d = L.prox(nome);
      if (L.eh(d, "<")) d = L.prox(L.fecharAngulo(d) - 1);
      if (!L.eh(d, "=")) continue;
      const fim = L.pularTipo(L.prox(d));
      apagar(t, i, fim);
      i = fim - 1; continue;
    }
    // asserção  expr :: Tipo   (mas não rótulo ::nome::)
    if (tk.v === "::") {
      const d = L.prox(i);
      if (t[d]?.tipo === "nome" && L.eh(L.prox(d), "::")) { i = L.prox(d); continue; }
      const anterior = t[L.ant(i)];
      if (!anterior || anterior.tipo === "palavra" && !["nil", "true", "false", "end"].includes(anterior.v)) continue;
      const fim = L.pularTipo(d);
      apagar(t, i, fim);
      i = fim - 1; continue;
    }
    // local a: T, b: T = ...   e   for i: number = 1, 10
    if (tk.v === "local" || tk.v === "for") {
      let k = L.prox(i);
      if (t[k]?.v === "function") continue;
      while (t[k]?.tipo === "nome") {
        let d = L.prox(k);
        if (L.eh(d, "<")) { const f = L.fecharAngulo(d); apagar(t, d, f); d = L.prox(f - 1); }   // <const>
        if (L.eh(d, ":")) { const fim = L.pularTipo(L.prox(d)); apagar(t, d, fim); d = L.prox(fim - 1); }
        if (!L.eh(d, ",")) break;
        k = L.prox(d);
      }
      continue;
    }
    if (tk.v === "function") { pendenteFuncao = true; continue; }
    // genéricos  function f<T>(
    if (pendenteFuncao && tk.v === "<") { const f = L.fecharAngulo(i); apagar(t, i, f); i = f - 1; continue; }
    if (pendenteFuncao && tk.v === "(") {
      pendenteFuncao = false;
      const fecha = L.fecharGrupo(i) - 1;
      // parâmetros
      for (let k = L.prox(i); k < fecha; k = L.prox(k)) {
        if ((t[k].tipo === "nome" || t[k].v === "...") && L.eh(L.prox(k), ":")) {
          const d = L.prox(k);
          const fim = Math.min(L.pularTipo(L.prox(d)), fecha);
          apagar(t, d, fim);
          k = fim - 1;
        }
      }
      // retorno  ): Tipo
      const d = L.prox(fecha);
      if (L.eh(d, ":")) { const fim = L.pularTipo(L.prox(d)); apagar(t, d, fim); }
      i = fecha; continue;
    }
    if (pendenteFuncao && tk.tipo !== "nome" && tk.v !== "." && tk.v !== ":") pendenteFuncao = false;
  }
}

function atribuicoesCompostas(t) {
  const L = new Leitor(t);
  const COMP = { "+=": "+", "-=": "-", "*=": "*", "/=": "/", "//=": "//", "%=": "%", "^=": "^", "..=": ".." };
  const FIM = new Set(["end", "else", "elseif", "until", ";"]);
  for (let i = 0; i < t.length; i++) {
    const op = COMP[t[i].v];
    if (!op || t[i].tipo !== "op") continue;
    // lado esquerdo: nome(.nome | :nome | [..] | (..))*
    let a = L.ant(i);
    for (;;) {
      const tk = t[a];
      if (!tk) break;
      if (tk.v === "]" || tk.v === ")") {
        const abre = tk.v === "]" ? "[" : "(";
        let prof = 0, j = a;
        for (; j >= 0; j--) {
          if (!significativo(t[j])) continue;
          if (t[j].v === tk.v) prof++;
          else if (t[j].v === abre && --prof === 0) break;
        }
        const ant = L.ant(j);
        if (t[ant] && (t[ant].tipo === "nome" || t[ant].v === "]" || t[ant].v === ")")) { a = ant; continue; }
        a = j; break;
      }
      if (tk.tipo === "nome") {
        const ant = L.ant(a);
        if (t[ant] && (t[ant].v === "." || t[ant].v === ":")) { a = L.ant(ant); continue; }
      }
      break;
    }
    const esquerda = t.slice(a, i).map((x) => x.v).join("").trim();
    // lado direito: até o fim da linha (profundidade 0) ou palavra que fecha bloco
    let b = L.prox(i), prof = 0;
    for (; b < t.length; b++) {
      const tk = t[b];
      if (tk.tipo === "espaco" && tk.v.includes("\n") && prof === 0) break;
      if (!significativo(tk)) continue;
      if ("([{".includes(tk.v) && tk.tipo === "op") prof++;
      else if (")]}".includes(tk.v) && tk.tipo === "op") { if (prof === 0) break; prof--; }
      else if (prof === 0 && FIM.has(tk.v)) break;
    }
    const direita = t.slice(L.prox(i), b).map((x) => x.v).join("").trim();
    for (let k = a; k < b; k++) t[k] = { tipo: "espaco", v: "" };
    const espaco = t[b] && significativo(t[b]) ? " " : "";
    t[a] = { tipo: "op", v: `${esquerda} = ${esquerda} ${op} (${direita})${espaco}` };
    i = b - 1;
  }
}

function interpolacao(t) {
  for (const tk of t) {
    if (tk.tipo !== "crase") continue;
    const s = tk.v.slice(1, -1);
    const partes = [];
    let lit = "", i = 0;
    while (i < s.length) {
      const c = s[i];
      if (c === "\\" && s[i + 1] === "{") { lit += "{"; i += 2; continue; }
      if (c === "\\") { lit += s.slice(i, i + 2); i += 2; continue; }
      if (c === "{") {
        let prof = 1, j = i + 1;
        while (j < s.length && prof > 0) { if (s[j] === "{") prof++; else if (s[j] === "}") prof--; j++; }
        if (lit) partes.push(`"${lit}"`);
        lit = "";
        partes.push(`__texto(${traduzirLuau(s.slice(i + 1, j - 1))})`);
        i = j; continue;
      }
      if (c === '"') { lit += '\\"'; i++; continue; }
      lit += c; i++;
    }
    if (lit || !partes.length) partes.push(`"${lit}"`);
    tk.tipo = "texto";
    tk.v = `(${partes.join(" .. ")})`;
  }
}

function continueParaGoto(t) {
  const L = new Leitor(t);
  const pilha = [];
  let pendenteLaco = false, pendenteIf = false, contador = 0;
  for (let i = 0; i < t.length; i++) {
    const tk = t[i];
    if (!significativo(tk)) continue;
    const v = tk.v;
    if (tk.tipo === "palavra") {
      if (v === "while" || v === "for") pendenteLaco = true;
      else if (v === "do") { pilha.push({ laco: pendenteLaco }); pendenteLaco = false; }
      else if (v === "if") pendenteIf = true;
      else if (v === "then" && pendenteIf) { pilha.push({ laco: false }); pendenteIf = false; }
      else if (v === "function") pilha.push({ funcao: true });
      else if (v === "repeat") pilha.push({ laco: true, repeat: true });
      else if (v === "end" || v === "until") {
        const bloco = pilha.pop();
        if (bloco?.rotulo) t[i] = { tipo: "op", v: `::${bloco.rotulo}:: ${v}` };
      }
      continue;
    }
    if (tk.tipo === "nome" && v === "continue") {
      const d = t[L.prox(i)];
      if (d && ["=", "(", ".", "[", ":", ",", "+=", "-="].includes(d.v)) continue;   // é uma variável
      let laco = null;
      for (let k = pilha.length - 1; k >= 0 && !pilha[k].funcao; k--) if (pilha[k].laco) { laco = pilha[k]; break; }
      if (!laco) continue;
      laco.rotulo = laco.rotulo || `__continue${++contador}`;
      t[i] = { tipo: "op", v: `goto ${laco.rotulo}` };
    }
  }
}

/** Luau -> Lua 5.3, mantendo as linhas. */
export function traduzirLuau(codigo) {
  const t = tokenizar(String(codigo));
  interpolacao(t);
  tirarTipos(t);
  atribuicoesCompostas(t);
  continueParaGoto(t);
  return t.map((x) => x.v).join("");
}
