// VISTA — placar do jogo (leaderstats).
// Mostra na tela os valores da pasta "leaderstats" do jogador e manda o 1º valor
// para o site como recorde (o site guarda o maior de cada jogador).

const NOME = /^[^<>]{1,32}$/;

export function lerLeaderstats(jogador) {
  const pasta = jogador?.FindFirstChild?.("leaderstats");
  if (!pasta) return [];
  return pasta.GetChildren()
    .filter((v) => (v.ClassName === "IntValue" || v.ClassName === "NumberValue") && NOME.test(v.Name))
    .slice(0, 4)
    .map((v) => ({ nome: v.Name, valor: Number(v.Value) || 0 }));
}

export function formatar(v) {
  return Number.isInteger(v) ? v.toLocaleString("pt-BR") : (Math.round(v * 10) / 10).toLocaleString("pt-BR");
}

export class Placar {
  constructor({ jogo, caixa, enviar = null, intervaloEnvio = 3000 }) {
    this.jogo = jogo;
    this.caixa = caixa;               // elemento onde o placar aparece
    this.enviar = enviar;             // async (estatistica, valor) => void  (null = modo teste, não envia)
    this.intervaloEnvio = intervaloEnvio;
    this.enviado = -Infinity;
    this.ultimoEnvio = 0;
    this.texto = "";
  }

  /** Chamado a cada quadro (depois de desenhar); só mexe na tela quando muda. */
  nomes() {
    const stats = lerLeaderstats(this.jogo.mundo.game.Players.LocalPlayer);
    const texto = stats.map((s) => `${s.nome}: ${formatar(s.valor)}`).join("\n");
    if (texto !== this.texto) {
      this.texto = texto;
      this.caixa.hidden = !stats.length;
      this.caixa.replaceChildren(...stats.map((s) => {
        const linha = document.createElement("div");
        const n = document.createElement("span"); n.textContent = s.nome;
        const v = document.createElement("b"); v.textContent = formatar(s.valor);
        linha.append(n, v);
        return linha;
      }));
    }
    const principal = stats[0];
    const agora = performance.now();
    if (this.enviar && principal && principal.valor > this.enviado && principal.valor > 0
        && agora - this.ultimoEnvio > this.intervaloEnvio) {
      this.ultimoEnvio = agora;
      const valor = principal.valor;
      this.enviar(principal.nome, valor).then(() => { this.enviado = Math.max(this.enviado, valor); }).catch(() => {});
    }
  }
}
