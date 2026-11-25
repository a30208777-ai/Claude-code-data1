// Vista Studio — render 3D (Three.js). Modo "leve" (celular) e "pesado" (PC).

import * as THREE from "three";
import { OBJLoader } from "three/addons/OBJLoader.js";
import { MTLLoader } from "three/addons/MTLLoader.js";
import { BasePart } from "./motor.js";
import { criarMaterial, ajustarMaterial, corDoCeu } from "./materiais.js";

export class Render {
  constructor(canvas, mundo, modo) {
    this.modo = modo;
    this.pesado = modo === "pesado";
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: this.pesado, powerPreference: this.pesado ? "high-performance" : "low-power" });
    this.renderer.setPixelRatio(this.pesado ? Math.min(devicePixelRatio, 2) : 1);
    this.renderer.shadowMap.enabled = this.pesado;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.cena = new THREE.Scene();
    this.cena.background = new THREE.Color("#9fd3ff");
    this.camera = new THREE.PerspectiveCamera(70, 1, 0.1, 2000);
    this.camera.position.set(20, 18, 24);
    this.camera.lookAt(0, 0, 0);
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x556655, this.pesado ? 1.6 : 2.2);
    this.cena.add(this.hemi);
    const sol = this.sol = new THREE.DirectionalLight(0xffffff, this.pesado ? 2.2 : 1.2);
    sol.position.set(40, 80, 30);
    if (this.pesado) {
      sol.castShadow = true;
      sol.shadow.mapSize.set(2048, 2048);
      Object.assign(sol.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, far: 300 });
    }
    this.cena.add(sol);
    this.grade = new THREE.GridHelper(256, this.pesado ? 128 : 64, 0x335533, 0x335533);
    this.grade.material.opacity = 0.18; this.grade.material.transparent = true;
    this.cena.add(this.grade);
    this.objetos = new Map();      // id da instância -> Object3D
    this.geoCaixa = new THREE.BoxGeometry(1, 1, 1);
    this.geoBola = new THREE.SphereGeometry(0.5, this.pesado ? 32 : 12, this.pesado ? 16 : 8);
    this.geoCil = new THREE.CylinderGeometry(0.5, 0.5, 1, this.pesado ? 32 : 12);
    this.cacheMalhas = new Map();
    this.efeitos = [];             // clarões, confetes... (somem sozinhos)
    this.definirMundo(mundo);
  }

  definirMundo(mundo) {
    for (const o of this.objetos.values()) this.cena.remove(o);
    this.objetos.clear();
    this.mundo = mundo;
    this.ligados = this.ligados || new WeakSet();
    if (!this.ligados.has(mundo)) {
      this.ligados.add(mundo);
      mundo.on("entrou", (i) => { if (this.mundo === mundo) this.criar(i); });
      mundo.on("saiu", (i) => { if (this.mundo === mundo) this.remover(i); });
      mundo.on("mudou", (i, p) => {
        if (this.mundo !== mundo) return;
        if (i.ClassName === "Ceu") this.aplicarCeu(i); else this.atualizar(i, p);
      });
      try { mundo.game.Efeitos.Mostrar.Connect((tipo, alvo, n) => { if (this.mundo === mundo) this.efeito(tipo, alvo, n); }); }
      catch { /* mundo sem Efeitos */ }
    }
    for (const p of mundo.partes()) this.criar(p);
    try { this.aplicarCeu(mundo.game.Ceu); } catch { /* mundo antigo */ }
  }

  /** Hora do dia, neblina e estrelas (serviço Ceu). */
  aplicarCeu(ceu) {
    const { ceu: cor, luz, forca } = corDoCeu(ceu.Hora);
    this.cena.background = cor;
    this.sol.color = luz;
    this.sol.intensity = (this.pesado ? 2.2 : 1.2) * forca;
    this.hemi.intensity = (this.pesado ? 1.6 : 2.2) * (0.35 + 0.65 * forca);
    const ang = ((ceu.Hora - 6) / 12) * Math.PI;                  // sol nasce às 6 e se põe às 18
    this.sol.position.set(Math.cos(ang) * 80, Math.max(10, Math.sin(ang) * 90), 30);
    if (ceu.Neblina > 0) this.cena.fog = new THREE.Fog(cor, 10, 700 - 640 * ceu.Neblina);
    else this.cena.fog = null;
    const noite = forca < 0.35 && ceu.Estrelas;
    if (noite && !this.estrelas) {
      const n = this.pesado ? 1500 : 500, pos = new Float32Array(n * 3);
      for (let k = 0; k < n; k++) {
        const t = Math.random() * Math.PI * 2, f = Math.acos(Math.random() * 0.9), r = 900;
        pos.set([r * Math.sin(f) * Math.cos(t), r * Math.cos(f), r * Math.sin(f) * Math.sin(t)], k * 3);
      }
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      this.estrelas = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: this.pesado ? 2 : 3, sizeAttenuation: false, fog: false }));
      this.cena.add(this.estrelas);
    }
    if (this.estrelas) this.estrelas.visible = noite;
  }

  /** Efeitos especiais pedidos pelos scripts (serviço Efeitos). */
  efeito(tipo, alvo, n) {
    if (this.efeitos.length > 40) return;
    const agora = performance.now();
    if (tipo === "brilho") {
      const o = this.objetos.get(alvo?.id);
      if (o?.material) this.efeitos.push({ tipo, o, ini: agora, dur: n * 1000, antes: o.material.emissiveIntensity, cor: o.material.emissive?.clone() });
      return;
    }
    const pos = new THREE.Vector3(alvo.X, alvo.Y, alvo.Z);
    if (tipo === "explosao") {
      const bola = new THREE.Mesh(this.geoBola, new THREE.MeshBasicMaterial({ color: 0xffa000, transparent: true, opacity: 0.9 }));
      bola.position.copy(pos); this.cena.add(bola);
      const luz = new THREE.PointLight(0xffaa33, 30, n * 4); luz.position.copy(pos); this.cena.add(luz);
      this.efeitos.push({ tipo, objs: [bola, luz], ini: agora, dur: 600, raio: n });
      return;
    }
    // confete e fumaça: partículas simples
    const qtd = tipo === "confete" ? (this.pesado ? 160 : 70) : (this.pesado ? 40 : 20);
    const g = new THREE.BufferGeometry(), p = new Float32Array(qtd * 3), cores = new Float32Array(qtd * 3), vel = [];
    const paleta = [0xff4081, 0xffc400, 0x00e5ff, 0x76ff03, 0xd500f9, 0xff6d00].map((c) => new THREE.Color(c));
    for (let k = 0; k < qtd; k++) {
      p.set([pos.x, pos.y, pos.z], k * 3);
      const c = tipo === "confete" ? paleta[k % paleta.length] : new THREE.Color(0x9e9e9e);
      cores.set([c.r, c.g, c.b], k * 3);
      vel.push(tipo === "confete"
        ? new THREE.Vector3((Math.random() - 0.5) * 30, 20 + Math.random() * 25, (Math.random() - 0.5) * 30)
        : new THREE.Vector3((Math.random() - 0.5) * 4, 3 + Math.random() * 4, (Math.random() - 0.5) * 4));
    }
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    g.setAttribute("color", new THREE.BufferAttribute(cores, 3));
    const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: tipo === "confete" ? 0.5 : 2.5, vertexColors: true, transparent: true, opacity: tipo === "confete" ? 1 : 0.6 }));
    this.cena.add(pts);
    this.efeitos.push({ tipo, objs: [pts], vel, ini: agora, ultimo: agora, dur: tipo === "confete" ? 2500 : 2000 });
  }

  _animarEfeitos() {
    const agora = performance.now();
    this.efeitos = this.efeitos.filter((e) => {
      const t = Math.min(1, (agora - e.ini) / e.dur);
      if (e.tipo === "explosao") {
        const [bola, luz] = e.objs;
        bola.scale.setScalar(Math.max(0.01, e.raio * 2 * Math.sqrt(t)));
        bola.material.opacity = 0.9 * (1 - t); luz.intensity = 30 * (1 - t);
      } else if (e.tipo === "brilho") {
        if (e.o.material) {
          e.o.material.emissive.set(0xffffff);
          e.o.material.emissiveIntensity = 0.8 * Math.abs(Math.sin(t * Math.PI * 6));
        }
      } else {
        const dt = (agora - e.ultimo) / 1000; e.ultimo = agora;
        const attr = e.objs[0].geometry.attributes.position;
        e.vel.forEach((v, k) => {
          if (e.tipo === "confete") v.y -= 30 * dt;
          attr.array[k * 3] += v.x * dt; attr.array[k * 3 + 1] += v.y * dt; attr.array[k * 3 + 2] += v.z * dt;
        });
        attr.needsUpdate = true;
        e.objs[0].material.opacity = (e.tipo === "confete" ? 1 : 0.6) * (1 - t * t);
      }
      if (t < 1) return true;
      if (e.tipo === "brilho") {
        if (e.o.material) { e.o.material.emissiveIntensity = e.antes ?? 0; if (e.cor) e.o.material.emissive.copy(e.cor); }
      } else {
        for (const o of e.objs) {
          this.cena.remove(o);
          if (o.geometry && o.geometry !== this.geoBola) o.geometry.dispose();   // a bola é compartilhada
          o.material?.dispose?.();
        }
      }
      return false;
    });
  }

  geometria(p) {
    if (p.Shape === "Ball") return this.geoBola;
    if (p.Shape === "Cylinder") return this.geoCil;
    return this.geoCaixa;
  }

  criar(i) {
    if (!(i instanceof BasePart) || this.objetos.has(i.id)) return;
    if (!i.IsDescendantOf(this.mundo.workspace)) return;
    let obj;
    if (i.ClassName === "MeshPart" && i.MeshId && this.mundo.assets[i.MeshId]) {
      obj = new THREE.Group();
      this.carregarMalha(i.MeshId).then((malha) => {
        if (!malha || !this.objetos.has(i.id)) return;
        obj.add(malha.clone(true));
        this.atualizar(i, "Size");
      });
    } else {
      obj = new THREE.Mesh(this.geometria(i), criarMaterial(i, this.pesado));
      obj.castShadow = this.pesado; obj.receiveShadow = this.pesado;
    }
    obj.userData.instancia = i;
    this.objetos.set(i.id, obj);
    this.cena.add(obj);
    this.atualizar(i);
  }

  remover(i) {
    const o = this.objetos.get(i.id);
    if (o) { this.cena.remove(o); this.objetos.delete(i.id); if (o.material) { o.material.map?.dispose(); o.material.dispose(); } }
  }

  atualizar(i, prop) {
    if (prop === "Parent") {
      const dentro = i instanceof BasePart && i.IsDescendantOf(this.mundo.workspace);
      if (dentro && !this.objetos.has(i.id)) this.criar(i);
      if (!dentro) this.remover(i);
      return;
    }
    const o = this.objetos.get(i.id);
    if (!o) return;
    o.position.set(i.Position.X, i.Position.Y, i.Position.Z);
    const r = i.Rotation, rad = Math.PI / 180;
    o.rotation.set(r.X * rad, r.Y * rad, r.Z * rad);
    if (o.isMesh) {
      o.scale.set(i.Size.X, i.Size.Y, i.Size.Z);
      if (prop === "Shape") o.geometry = this.geometria(i);
      if (prop === "Material" && o.material.userData.material !== i.Material) {
        o.material.map?.dispose(); o.material.dispose();
        o.material = criarMaterial(i, this.pesado);
      }
      ajustarMaterial(o.material, i);
      o.visible = i.Transparency < 1;
    } else {
      const base = o.userData.tamanhoBase;
      if (base) o.scale.set(i.Size.X / base.x, i.Size.Y / base.y, i.Size.Z / base.z);
      o.visible = i.Transparency < 1;
    }
  }

  /** Malha .obj importada (centralizada; guarda o tamanho original). */
  async carregarMalha(id) {
    if (this.cacheMalhas.has(id)) return this.cacheMalhas.get(id);
    const asset = this.mundo.assets[id];
    const prom = (async () => {
      const urls = {};
      for (const [n, dataUrl] of Object.entries(asset.texturas || {})) urls[n.toLowerCase()] = dataUrl;
      const gerente = new THREE.LoadingManager();
      gerente.setURLModifier((u) => urls[u.split(/[\\/]/).pop().toLowerCase()] || u);
      const objLoader = new OBJLoader(gerente);
      if (asset.mtl) {
        const mats = new MTLLoader(gerente).parse(asset.mtl, "");
        mats.preload();
        objLoader.setMaterials(mats);
      }
      const g = objLoader.parse(asset.obj);
      g.traverse((c) => { if (c.isMesh) { c.castShadow = this.pesado; c.receiveShadow = this.pesado; } });
      const caixa = new THREE.Box3().setFromObject(g);
      const centro = caixa.getCenter(new THREE.Vector3());
      g.position.sub(centro);
      const embrulho = new THREE.Group(); embrulho.add(g);
      const tam = caixa.getSize(new THREE.Vector3());
      embrulho.userData.tamanho = tam;
      return embrulho;
    })();
    this.cacheMalhas.set(id, prom);
    return prom;
  }

  redimensionar() {
    const c = this.renderer.domElement;
    const w = c.clientWidth, h = c.clientHeight;
    if (!w || !h) return;
    if (c.width !== Math.floor(w * this.renderer.getPixelRatio()) || c.height !== Math.floor(h * this.renderer.getPixelRatio())) {
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    }
  }

  desenhar() {
    this.redimensionar();
    // MeshPart: escala a malha para o Size
    for (const o of this.objetos.values()) {
      const i = o.userData.instancia;
      if (!o.isMesh && o.children[0]?.userData.tamanho) {
        const t = o.children[0].userData.tamanho;
        o.scale.set(i.Size.X / (t.x || 1), i.Size.Y / (t.y || 1), i.Size.Z / (t.z || 1));
      }
    }
    // água anda devagar
    const seg = performance.now() / 1000;
    for (const o of this.objetos.values()) {
      if (o.material?.userData?.material === "Agua" && o.material.map) o.material.map.offset.set(seg * 0.05, seg * 0.03);
    }
    if (this.efeitos.length) this._animarEfeitos();
        this.renderer.render(this.cena, this.camera);
  }

  /** Raio do toque/clique para selecionar uma peça. */
  pegar(xNorm, yNorm) {
    const r = new THREE.Raycaster();
    r.setFromCamera(new THREE.Vector2(xNorm, yNorm), this.camera);
    const hits = r.intersectObjects([...this.objetos.values()], true);
    for (const h of hits) {
      let o = h.object;
      while (o && !o.userData.instancia) o = o.parent;
      if (o && o.visible) return o.userData.instancia;
    }
    return null;
  }

  /** Ponto onde o raio do dedo/mouse cruza o plano horizontal y (para arrastar peças). */
  pontoNoPlano(xNorm, yNorm, y) {
    const r = new THREE.Raycaster();
    r.setFromCamera(new THREE.Vector2(xNorm, yNorm), this.camera);
    const p = new THREE.Vector3();
    return r.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -y), p) ? p : null;
  }

  objetoDe(i) { return this.objetos.get(i?.id); }

  /**
   * Até onde dá para "enxergar" a partir de `origem` na direção `dir` (normalizada),
   * no máximo `max`. Ignora personagens, peças quase invisíveis e o Set `ignorar`.
   * Usado pela câmera do jogador para não atravessar paredes.
   */
  distanciaLivre(origem, dir, max, ignorar) {
    const r = this._raioLivre || (this._raioLivre = new THREE.Raycaster());
    r.set(new THREE.Vector3(origem.x, origem.y, origem.z), new THREE.Vector3(dir.x, dir.y, dir.z).normalize());
    r.near = 0; r.far = max;
    const hits = r.intersectObjects([...this.objetos.values()], true);
    for (const h of hits) {
      let o = h.object;
      while (o && !o.userData.instancia) o = o.parent;
      const i = o?.userData.instancia;
      if (!i || !o.visible || i._personagem || i._visual || ignorar?.has(i) || (i.Transparency ?? 0) >= 0.9) continue;
      return h.distance;
    }
    return max;
  }
}
