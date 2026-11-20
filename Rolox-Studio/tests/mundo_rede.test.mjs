// Mundo compartilhado (anfitrião -> convidados) e Rede, sem navegador: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { mundoInicial, salvarMundo, carregarMundo, criar, Vector3 } from "../static/studio/motor.js";
import { MundoRede } from "../static/studio/mundo_rede.js";

function mapa() {
  const m = mundoInicial();
  const porta = criar("Part", m.workspace); porta.Name = "Porta"; porta.Anchored = true;
  const pasta = criar("Folder", m.workspace); pasta.Name = "Moedas";
  for (let i = 0; i < 3; i++) { const c = criar("Part", pasta); c.Name = "Moeda"; }
  return salvarMundo(m);
}

function par() {
  const dados = mapa();
  const host = new MundoRede(carregarMundo(dados)), conv = new MundoRede(carregarMundo(dados));
  host.indexar(); conv.indexar(); host.ligar(); conv.ligar();
  host.modoAnfitriao(); host.colher();            // descarta o "estado inicial"
  conv.modoConvidado();
  return { host, conv };
}
const achar = (mr, nome) => mr.mundo.workspace.FindFirstChild(nome, true);

test("todos os aparelhos dão as mesmas chaves para o mesmo mapa", () => {
  const { host, conv } = par();
  assert.deepEqual([...host.porChave.keys()], [...conv.porChave.keys()]);
  assert.equal(host.chaveDe.get(achar(host, "Porta")), conv.chaveDe.get(achar(conv, "Porta")));
});

test("o anfitrião abre a porta e o convidado vê aberta", () => {
  const { host, conv } = par();
  const porta = achar(host, "Porta");
  porta.Transparency = 0.8; porta.CanCollide = false; porta.Position = new Vector3(0, 9, -12);
  const envio = host.colher();
  assert.equal(envio.m.length, 1);
  conv.aplicar(envio.m);
  const p2 = achar(conv, "Porta");
  assert.equal(p2.Transparency, 0.8); assert.equal(p2.CanCollide, false); assert.equal(p2.Position.Y, 9);
  assert.equal(host.colher(), null);              // nada novo
});

test("peça criada e apagada por Script no anfitrião aparece/some no convidado", () => {
  const { host, conv } = par();
  const bala = criar("Part"); bala.Name = "Bala"; bala.Parent = achar(host, "Moedas");
  achar(host, "Moedas").GetChildren()[0].Destroy();
  const envio = host.colher();
  conv.aplicar(envio.m);
  conv.aplicar(envio.d.map((k) => ({ k, x: 1 })));
  const pasta2 = achar(conv, "Moedas");
  assert.ok(pasta2.FindFirstChild("Bala"));
  assert.equal(pasta2.GetChildren().filter((c) => c.Name === "Moeda").length, 2);
  assert.ok(pasta2.FindFirstChild("Bala")._rede);   // no convidado, quem move é a rede
});

test("convidado não manda nada e personagens não entram no espelho", () => {
  const { host, conv } = par();
  achar(conv, "Porta").Transparency = 1;
  assert.equal(conv.colher(), null);
  const boneco = criar("Model"); boneco._temporaria = true; boneco.Parent = host.mundo.workspace;
  criar("Part", boneco);
  assert.equal(host.colher(), null);
});

test("Rede sozinho: ParaServidor chega no Recebido e ParaTodos no RecebidoDoServidor", async () => {
  const m = mundoInicial();
  const rede = m.game.GetService("Rede");
  const chegou = [];
  rede.Recebido.Connect((j, nome, dados) => chegou.push(["srv", nome, dados]));
  rede.RecebidoDoServidor.Connect((nome, dados) => chegou.push(["cli", nome, dados]));
  rede.ParaServidor("abrirPorta", 7);
  rede.ParaTodos("portaAberta", true);
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(chegou, [["srv", "abrirPorta", 7], ["cli", "portaAberta", true]]);
  assert.throws(() => rede.ParaServidor("<x>", 1));
  assert.throws(() => rede.ParaServidor("ok", { a: 1 }));
  // o projeto salvo não leva a Rede (é um serviço do jogo rodando)
  assert.ok(!("Rede" in salvarMundo(m).servicos));
});

test("Cofre: ler com padrão, salvar, somar, apagar e o que falta enviar", () => {
  const m = mundoInicial();
  const c = m.game.GetService("Cofre");
  c._carregar({ moedas: 5 });
  assert.equal(c.Ler("moedas", 0), 5);
  assert.equal(c.Ler("fase", "inicio"), "inicio");
  assert.equal(c.Somar("moedas", 2), 7);
  c.Salvar("fase", "lava"); c.Apagar("fase");
  assert.deepEqual(c._pendentes(), { moedas: 7, fase: null });
  assert.equal(c._pendentes(), null);
  assert.throws(() => c.Salvar("a b", 1)); assert.throws(() => c.Salvar("x", { t: 1 })); assert.throws(() => c.Salvar("x", NaN));
  assert.ok(!("Cofre" in salvarMundo(m).servicos));
});

test("Tela: texto, botão (clique), barra, aviso, remover; Sons validados", async () => {
  const m = mundoInicial();
  const tela = m.game.GetService("Tela"), sons = m.game.GetService("Sons");
  const visto = [], cliques = [], tocou = [];
  tela.Mudou.Connect((id, item) => visto.push([id, item && item.tipo]));
  tela.Clicado.Connect((id) => cliques.push(id));
  sons.Tocou.Connect((t, n) => tocou.push(t + ":" + n));
  tela.Texto("placar", "Moedas: 3", "topo");
  tela.Botao("abrir", "Abrir", "lugar-inventado");
  tela.Barra("vida", 150, 100);
  assert.equal(tela._itens.get("abrir").lugar, "baixo".replace("baixo", "topo"));   // lugar inválido vira topo
  assert.equal(tela._itens.get("vida").valor, 100);                                    // não passa do máximo
  tela._clicar("abrir"); tela._clicar("placar");                                       // texto não é clicável
  assert.deepEqual(cliques, ["abrir"]);
  tela.Remover("placar");
  assert.deepEqual(visto.slice(-1), [["placar", null]]);
  assert.throws(() => tela.Texto("<b>", "x"));
  sons.Tocar("moeda"); sons.Musica("calma"); sons.Musica("");
  assert.deepEqual(tocou, ["som:moeda", "musica:calma", "musica:"]);
  assert.throws(() => sons.Tocar("grito"));
  tela.Limpar();
  assert.equal(tela._itens.size, 0);
});
