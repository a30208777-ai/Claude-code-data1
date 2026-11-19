// Rolox Studio — render 3D (Three.js). Modo "leve" (celular) e "pesado" (PC).

import * as THREE from "three";
import { OBJLoader } from "three/addons/OBJLoader.js";
import { MTLLoader } from "three/addons/MTLLoader.js";
import { BasePart } from "./motor.js";

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
    this.cena.add(new THREE.HemisphereLight(0xffffff, 0x556655, this.pesado ? 1.6 : 2.2));
    const sol = new THREE.DirectionalLight(0xffffff, this.pesado ? 2.2 : 1.2);
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
      mundo.on("mudou", (i, p) => { if (this.mundo === mundo) this.atualizar(i, p); });
    }
    for (const p of mundo.partes()) this.criar(p);
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
      const mat = new THREE.MeshStandardMaterial({ color: i.Color.toHex(), roughness: 0.8 });
      obj = new THREE.Mesh(this.geometria(i), mat);
      obj.castShadow = this.pesado; obj.receiveShadow = this.pesado;
    }
    obj.userData.instancia = i;
    this.objetos.set(i.id, obj);
    this.cena.add(obj);
    this.atualizar(i);
  }

  remover(i) {
    const o = this.objetos.get(i.id);
    if (o) { this.cena.remove(o); this.objetos.delete(i.id); if (o.material) o.material.dispose(); }
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
      o.material.color.set(i.Color.toHex());
      o.material.transparent = i.Transparency > 0;
      o.material.opacity = 1 - i.Transparency;
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

  objetoDe(i) { return this.objetos.get(i?.id); }
}
