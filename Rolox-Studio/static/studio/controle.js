// Controle PCtoCelular (roda no celular). Manda ao PC, ~20x por segundo:
//   modo "sensor":   inclinação (frente/lado), giro, altura estimada e pulo (levantar rápido)
//   modo "joystick": controle padrão na tela (quando não há sensor ou o navegador bloqueia)
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const estado = { ws: null, modo: "joystick", x: 0, z: 0, pular: false, sensor: { alpha: 0, beta: 0, gamma: 0, altura: 0 },
    calib: null, vel: 0, altura: 0, ultimoPulo: 0 };

  const msg = (t, classe = "nota") => { const e = $("#estado"); e.textContent = t; e.className = classe; };
  try { $("#nome").value = localStorage.getItem("rolox-controle-nome") || ""; } catch { /* sem armazenamento */ }

  $("#conectar").addEventListener("click", conectar);
  $("#codigo").addEventListener("keydown", (e) => { if (e.key === "Enter") conectar(); });

  function conectar() {
    const codigo = $("#codigo").value.trim();
    if (!/^\d{4}$/.test(codigo)) { msg("O código tem 4 números.", "erro"); return; }
    try { localStorage.setItem("rolox-controle-nome", $("#nome").value.trim()); } catch { /* ok */ }
    msg("Conectando...");
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws/pc2cel/controle`);
    estado.ws = ws;
    let respondeu = false;
    ws.onopen = () => ws.send(JSON.stringify({ codigo, nome: $("#nome").value.trim() }));
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      respondeu = true;
      if (m.tipo === "erro") { msg(m.mensagem, "erro"); voltar(); }
      else if (m.tipo === "ok") { msg(`Conectado por ${m.via}.`, "ok"); comecar(m.via); }
    };
    ws.onclose = () => { if ($("#jogo").classList.contains("ativo")) { msg("Conexão encerrada.", "erro"); voltar(); } };
    ws.onerror = () => { if (!respondeu) msg("Não foi possível conectar. Confira o cabo/Bluetooth e o endereço.", "erro"); };
  }

  function voltar() { $("#jogo").classList.remove("ativo"); $("#entrar").hidden = false; clearInterval(estado.timer); }

  async function comecar(via) {
    $("#entrar").hidden = true;
    $("#jogo").classList.add("ativo");
    const temSensor = await pedirSensor();
    usarModo(temSensor ? "sensor" : "joystick", via);
    estado.timer = setInterval(enviar, 50);
  }

  // ------------------------------------------------------------- sensor
  async function pedirSensor() {
    if (!("DeviceOrientationEvent" in window) || !window.isSecureContext) return false;
    try {
      if (typeof DeviceOrientationEvent.requestPermission === "function") {        // iPhone
        if ((await DeviceOrientationEvent.requestPermission()) !== "granted") return false;
        if (typeof DeviceMotionEvent?.requestPermission === "function") await DeviceMotionEvent.requestPermission();
      }
    } catch { return false; }
    return new Promise((ok) => {
      let recebeu = false;
      const teste = (e) => { if (e.beta != null || e.gamma != null) { recebeu = true; } };
      addEventListener("deviceorientation", teste);
      setTimeout(() => { removeEventListener("deviceorientation", teste); ok(recebeu); }, 700);
    });
  }

  addEventListener("deviceorientation", (e) => {
    if (e.beta == null) return;
    const s = estado.sensor;
    s.alpha = e.alpha || 0; s.beta = e.beta; s.gamma = e.gamma || 0;
    if (!estado.calib) estado.calib = { beta: s.beta, gamma: s.gamma };
    if (estado.modo !== "sensor") return;
    const zona = 6, max = 30;                       // graus
    const eixo = (v) => (Math.abs(v) < zona ? 0 : Math.max(-1, Math.min(1, (v - Math.sign(v) * zona) / (max - zona))));
    estado.z = -eixo(s.beta - estado.calib.beta);   // inclinar para frente = andar para frente
    estado.x = eixo(s.gamma - estado.calib.gamma);
    $("#la").textContent = s.alpha.toFixed(0); $("#lb").textContent = estado.z.toFixed(2); $("#lg").textContent = estado.x.toFixed(2);
  });

  // altura: integra a aceleração vertical (com perda, para não "andar sozinha");
  // levantar o celular rápido = pular
  addEventListener("devicemotion", (e) => {
    if (estado.modo !== "sensor") return;
    const a = e.acceleration?.z ?? (e.accelerationIncludingGravity ? e.accelerationIncludingGravity.z - 9.81 : null);
    if (a == null) return;
    const dt = (e.interval || 16) / 1000;
    estado.vel = (estado.vel + a * dt) * 0.92;
    estado.altura = (estado.altura + estado.vel * dt) * 0.98;
    estado.sensor.altura = estado.altura;
    $("#lh").textContent = (estado.altura * 100).toFixed(0) + "cm";
    const agora = performance.now();
    if (a > 6 && agora - estado.ultimoPulo > 600) { estado.ultimoPulo = agora; estado.pular = true; setTimeout(() => (estado.pular = false), 200); }
  });

  function usarModo(modo, via) {
    estado.modo = modo; estado.x = 0; estado.z = 0; estado.calib = null;
    $("#joystick").hidden = modo !== "joystick";
    $("#dicaSensor").hidden = modo !== "sensor";
    $("#leituras").hidden = modo !== "sensor";
    $("#trocar").textContent = modo === "sensor" ? "Usar joystick" : "Usar movimento do celular";
    $("#modo").textContent = modo === "sensor"
      ? `Modo movimento${via ? " · " + via : ""}. Segure o celular reto e incline para andar.`
      : `Controle padrão${via ? " · " + via : ""} (joystick).` +
        (!window.isSecureContext ? " O sensor só funciona em conexão segura (cabo com adb reverse usa localhost, que é seguro)." : "");
  }
  $("#trocar").addEventListener("click", async () => {
    if (estado.modo === "sensor") usarModo("joystick");
    else if (await pedirSensor()) usarModo("sensor");
    else $("#modo").textContent = "Este celular/navegador não liberou o sensor de movimento. Continuando no joystick.";
  });

  // ------------------------------------------------------------ joystick
  const base = $("#joystick"), manche = $("#manche");
  let ponteiro = null;
  const mover = (e) => {
    const r = base.getBoundingClientRect();
    let dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2), dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    const m = Math.hypot(dx, dy); if (m > 1) { dx /= m; dy /= m; }
    manche.style.transform = `translate(${dx * 60}px, ${dy * 60}px)`;
    estado.x = dx; estado.z = -dy;
  };
  const area = $("#areaControle");
  area.addEventListener("pointerdown", (e) => { if (estado.modo !== "joystick") return; ponteiro = e.pointerId; area.setPointerCapture(ponteiro); mover(e); });
  area.addEventListener("pointermove", (e) => { if (e.pointerId === ponteiro) mover(e); });
  const soltar = () => { ponteiro = null; manche.style.transform = ""; if (estado.modo === "joystick") { estado.x = 0; estado.z = 0; } };
  area.addEventListener("pointerup", soltar); area.addEventListener("pointercancel", soltar);

  const pular = $("#pular");
  pular.addEventListener("pointerdown", () => { estado.pular = true; navigator.vibrate?.(20); });
  pular.addEventListener("pointerup", () => { estado.pular = false; });

  function enviar() {
    const ws = estado.ws;
    if (!ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ x: estado.x, z: estado.z, pular: estado.pular, modo: estado.modo,
      sensor: estado.modo === "sensor" ? estado.sensor : null }));
  }
})();
