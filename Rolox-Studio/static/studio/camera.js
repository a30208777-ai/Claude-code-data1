// ROLOX — câmera do jogador (terceira pessoa).
//
//  * segue o personagem de forma suave (sem tremer);
//  * girar: arrastar na tela (dedo ou mouse) ou teclas Q/E;
//  * zoom: roda do mouse, pinça com dois dedos ou teclas I/O;
//  * não atravessa paredes: se algo fica entre o jogador e a câmera, ela chega perto;
//  * bem perto (zoom máximo) vira primeira pessoa.
//
// Dois toques rápidos na tela recentralizam a câmera.
//
// Os toques no joystick e no botão de pular não giram a câmera (eles ficam em
// elementos por cima do canvas, então os eventos nem chegam aqui).

const PI2 = Math.PI * 2;
const limitar = (v, a, b) => Math.min(b, Math.max(a, v));

export class CameraJogador {
  constructor(render, { distancia = 14, minimo = 0.5, maximo = 45 } = {}) {
    this.render = render;
    this.camera = render.camera;
    this.yaw = 0;                 // giro em volta do jogador (radianos)
    this.pitch = 0.42;            // inclinação (0 = horizontal, sobe até ~80°)
    this.distancia = distancia;   // zoom desejado
    this.atual = distancia;       // zoom usado (encurta perto de paredes)
    this.minimo = minimo;
    this.maximo = maximo;
    this.foco = null;             // ponto seguido (suavizado)
    this.ponteiros = new Map();
    this.pincaInicial = null;
    this.teclas = new Set();
    this._ligado = null;
  }

  get primeiraPessoa() { return this.distancia < 1.2; }

  ligar(elemento) {
    if (this._ligado) return;
    const el = elemento;
    const baixo = (e) => {
      if (e.pointerType === "mouse" && e.button !== 0 && e.button !== 2) return;
      // dois toques rápidos no mesmo lugar: câmera volta ao normal
      const agora = performance.now(), ult = this._ultimoToque;
      if (ult && agora - ult.t < 320 && Math.hypot(e.clientX - ult.x, e.clientY - ult.y) < 30) this.recentralizar();
      this._ultimoToque = { t: agora, x: e.clientX, y: e.clientY };
      this.ponteiros.set(e.pointerId, { x: e.clientX, y: e.clientY });
      el.setPointerCapture?.(e.pointerId);
      if (this.ponteiros.size === 2) this.pincaInicial = { d: this._distPonteiros(), zoom: this.distancia };
    };
    const mover = (e) => {
      const p = this.ponteiros.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      if (this.ponteiros.size >= 2 && this.pincaInicial) {
        const d = this._distPonteiros();
        if (d > 10) this.distancia = limitar(this.pincaInicial.zoom * (this.pincaInicial.d / d), this.minimo, this.maximo);
        return;
      }
      const sens = e.pointerType === "touch" ? 0.008 : 0.006;
      this.yaw = (this.yaw - dx * sens) % PI2;
      this.pitch = limitar(this.pitch + dy * sens, -0.3, 1.1);   // não deixa virar "vista de cima"
    };
    const cima = (e) => {
      this.ponteiros.delete(e.pointerId);
      if (this.ponteiros.size < 2) this.pincaInicial = null;
    };
    const roda = (e) => {
      e.preventDefault();
      this.distancia = limitar(this.distancia * Math.exp(e.deltaY * 0.0015), this.minimo, this.maximo);
    };
    const menu = (e) => e.preventDefault();          // botão direito também gira
    const tecla = (e) => {
      const k = e.key.toLowerCase();
      if (e.target?.closest?.("input, textarea")) return;
      if (e.type === "keydown") this.teclas.add(k); else this.teclas.delete(k);
    };
    el.addEventListener("pointerdown", baixo);
    el.addEventListener("pointermove", mover);
    el.addEventListener("pointerup", cima);
    el.addEventListener("pointercancel", cima);
    el.addEventListener("wheel", roda, { passive: false });
    el.addEventListener("contextmenu", menu);
    addEventListener("keydown", tecla);
    addEventListener("keyup", tecla);
    el.style.touchAction = "none";
    this._ligado = () => {
      el.removeEventListener("pointerdown", baixo);
      el.removeEventListener("pointermove", mover);
      el.removeEventListener("pointerup", cima);
      el.removeEventListener("pointercancel", cima);
      el.removeEventListener("wheel", roda);
      el.removeEventListener("contextmenu", menu);
      removeEventListener("keydown", tecla);
      removeEventListener("keyup", tecla);
    };
  }

  desligar() {
    this._ligado?.();
    this._ligado = null;
    this.ponteiros.clear();
    this.teclas.clear();
  }

  _distPonteiros() {
    const [a, b] = [...this.ponteiros.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  /** Volta para a inclinação e o zoom padrão (sem mexer no giro). */
  recentralizar() {
    this.pitch = 0.42;
    if (this.distancia < 4 || this.distancia > 30) this.distancia = 14;
  }

  /** Começa atrás do jogador, olhando para a frente do mapa. */
  posicionarAtras(alvo) {
    this.foco = { x: alvo.X, y: alvo.Y + 1.5, z: alvo.Z };
  }

  /**
   * Atualiza a câmera.
   * @param alvo posição do personagem ({X, Y, Z})
   * @param dt segundos desde o último quadro
   * @param ignorar Set de instâncias que não bloqueiam a visão (o próprio personagem)
   */
  atualizar(alvo, dt, ignorar) {
    // teclado: Q/E giram, I/O zoom
    const t = this.teclas;
    if (t.has("q")) this.yaw += 2.2 * dt;
    if (t.has("e")) this.yaw -= 2.2 * dt;
    if (t.has("i")) this.distancia = limitar(this.distancia * (1 - 1.5 * dt), this.minimo, this.maximo);
    if (t.has("o")) this.distancia = limitar(this.distancia * (1 + 1.5 * dt), this.minimo, this.maximo);

    // foco suave: segue rápido no chão, amortece pulos e quedas
    const destino = { x: alvo.X, y: alvo.Y + 1.5, z: alvo.Z };
    if (!this.foco || Math.hypot(destino.x - this.foco.x, destino.y - this.foco.y, destino.z - this.foco.z) > 30) {
      this.foco = { ...destino };               // teleporte / renascer: sem "voar" até lá
    }
    const kXZ = 1 - Math.exp(-18 * dt), kY = 1 - Math.exp(-8 * dt);
    this.foco.x += (destino.x - this.foco.x) * kXZ;
    this.foco.z += (destino.z - this.foco.z) * kXZ;
    this.foco.y += (destino.y - this.foco.y) * kY;

    // direção da câmera
    const cp = Math.cos(this.pitch);
    const dir = { x: Math.sin(this.yaw) * cp, y: Math.sin(this.pitch), z: Math.cos(this.yaw) * cp };

    // parede no caminho? encurta (com margem), e volta devagar quando liberar
    let livre = this.distancia;
    if (!this.primeiraPessoa && this.render.distanciaLivre) {
      const d = this.render.distanciaLivre(this.foco, dir, this.distancia, ignorar);
      if (d < this.distancia) livre = Math.max(this.minimo, d - 0.4);   // margem só quando bate
    }
    this.atual = livre < this.atual ? livre : this.atual + (livre - this.atual) * (1 - Math.exp(-4 * dt));

    if (this.primeiraPessoa) {
      const olho = { x: alvo.X, y: alvo.Y + 1.6, z: alvo.Z };
      this.camera.position.set(olho.x, olho.y, olho.z);
      this.camera.lookAt(olho.x - dir.x, olho.y - dir.y, olho.z - dir.z);
    } else {
      this.camera.position.set(this.foco.x + dir.x * this.atual, this.foco.y + dir.y * this.atual,
                               this.foco.z + dir.z * this.atual);
      this.camera.lookAt(this.foco.x, this.foco.y, this.foco.z);
    }
  }
}
