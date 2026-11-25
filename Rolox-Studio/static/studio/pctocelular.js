// Vista Studio — PCtoCelular (lado do PC).
//
// Celulares ligados ao PC por CABO (USB, via "adb reverse") ou BLUETOOTH
// (ancoragem Bluetooth) abrem a página /controle e mandam a inclinação,
// a altura estimada e os botões. Tudo fica na rede local entre o celular e o
// PC: o servidor do Studio só repassa as mensagens para esta página, na
// memória, e não grava nem envia para lugar nenhum.
// Limite: até 5 celulares por Bluetooth e 2 por cabo.

export const LIMITES = { bluetooth: 5, cabo: 2 };

export const ehCelular = () =>
  /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
  (navigator.maxTouchPoints > 1 && matchMedia("(pointer: coarse)").matches && innerWidth < 900);

export class PCtoCelular {
  constructor(aoMudar = () => {}) {
    this.aoMudar = aoMudar;
    this.celulares = new Map();   // id -> {id, nome, via, x, z, pular, sensor}
    this.codigo = null;
    this.urls = [];
    this.estado = "desconectado";
  }

  conectar() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    this.ws = new WebSocket(`${proto}//${location.host}/ws/pc2cel/host`);
    this.ws.onopen = () => { this.estado = "aguardando"; this.aoMudar(); };
    this.ws.onclose = () => { this.estado = "desconectado"; this.celulares.clear(); this.aoMudar(); };
    this.ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.tipo === "codigo") { this.codigo = m.codigo; this.urls = m.urls || []; }
      else if (m.tipo === "entrou") this.celulares.set(m.id, { id: m.id, nome: m.nome, via: m.via, x: 0, z: 0, pular: false, sensor: null });
      else if (m.tipo === "saiu") this.celulares.delete(m.id);
      else if (m.tipo === "dados") {
        const c = this.celulares.get(m.id);
        if (c) Object.assign(c, { x: clamp(m.x), z: clamp(m.z), pular: !!m.pular, sensor: m.sensor || null, modo: m.modo });
        return;   // dados chegam ~20x por segundo: não redesenha a lista
      }
      this.aoMudar();
    };
  }

  controles() { return [...this.celulares.values()]; }
  contagem() {
    const c = { bluetooth: 0, cabo: 0 };
    for (const x of this.celulares.values()) c[x.via] = (c[x.via] || 0) + 1;
    return c;
  }
  fechar() { this.ws?.close(); }
}

const clamp = (v) => Math.max(-1, Math.min(1, +v || 0));
