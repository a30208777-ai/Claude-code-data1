"""Multijogador do ROLOX: posição de quem está no mesmo servidor de jogo.

Cada jogador manda o próprio estado (posição, giro, se está andando) umas 7x por
segundo e recebe o dos outros. A sala fica num arquivo JSON por servidor, com
trava (fcntl), para funcionar com vários processos do gunicorn na mesma máquina.

Quem pode estar numa sala é decidido UMA vez, ao abrir /jogar (o Supabase confirma
que o jogador está no servidor). Ele recebe um passe assinado com o segredo do site
(servidor, usuário, nome, avatar), e as atualizações só checam esse passe:
nada de Supabase a cada quadro.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer

SUMIU_APOS = 6.0            # segundos sem atualizar: sai da sala
MAX_JOGADORES = 100
LIMITE_COORD = 100_000.0
SALA_VALIDA = re.compile(r"^[A-Za-z0-9-]{1,64}$")

# ---- mundo compartilhado (anfitrião) e Rede
MAX_EVENTOS = 20                 # por troca
MAX_CAIXA = 200                  # mensagens esperando por jogador
MAX_MUNDO = 4000                 # peças guardadas por sala
MAX_ITENS_ENVIO = 300
MAX_RESPOSTA_MUNDO = 1000
CHAVE = re.compile(r"^(w(/\d{1,4}){0,12}|n\d{1,7}-[a-z0-9]{1,6})$")
CLASSES = {"Part", "SpawnLocation", "Model", "Folder"}
NOME_EVENTO = re.compile(r"^[A-Za-z0-9_À-ÿ -]{1,40}$")
COR = re.compile(r"^#[0-9a-fA-F]{6}$")
UID = re.compile(r"^[0-9a-f-]{36}$")


def _vetor(v):
    if isinstance(v, list) and len(v) == 3:
        n = [_num(x, None) for x in v]
        if None not in n:
            return [round(x, 3) for x in n]
    return None


def limpar_props(props) -> dict:
    """Só as propriedades replicadas, com tipos e limites certos."""
    if not isinstance(props, dict):
        return {}
    r = {}
    for k in ("Position", "Rotation", "Size"):
        if k in props and (v := _vetor(props[k])) is not None:
            r[k] = v
    if isinstance(props.get("Color"), str) and COR.match(props["Color"]):
        r["Color"] = props["Color"]
    if "Transparency" in props:
        t = _num(props["Transparency"], None)
        if t is not None:
            r["Transparency"] = max(0.0, min(1.0, t))
    for k in ("CanCollide", "Anchored"):
        if isinstance(props.get(k), bool):
            r[k] = props[k]
    if props.get("Shape") in ("Block", "Ball", "Cylinder"):
        r["Shape"] = props["Shape"]
    if isinstance(props.get("Name"), str):
        r["Name"] = props["Name"][:60]
    return r


def _gravar_mundo(dados: dict, mudancas: dict) -> None:
    lista = mudancas.get("m") if isinstance(mudancas.get("m"), list) else []
    apagar = mudancas.get("d") if isinstance(mudancas.get("d"), list) else []
    mundo = dados["mundo"]
    for it in lista[:MAX_ITENS_ENVIO]:
        if not isinstance(it, dict) or not isinstance(it.get("k"), str) or not CHAVE.match(it["k"]):
            continue
        k = it["k"]
        atual = mundo.get(k)
        if atual is None and len(mundo) >= MAX_MUNDO:
            continue
        dados["v"] += 1
        novo = {"props": {**((atual or {}).get("props") or {}), **limpar_props(it.get("props"))}, "v": dados["v"]}
        if it.get("c") in CLASSES:
            p = it.get("p")
            novo.update(c=it["c"], p=p if isinstance(p, str) and CHAVE.match(p) else "w")
        elif atual and atual.get("c"):
            novo.update(c=atual["c"], p=atual.get("p", "w"))
        mundo[k] = novo
    for k in apagar[:MAX_ITENS_ENVIO]:
        if isinstance(k, str) and CHAVE.match(k) and k != "w":
            dados["v"] += 1
            mundo[k] = {"x": 1, "v": dados["v"]}


def _evento_valido(ev) -> Optional[dict]:
    if not isinstance(ev, dict) or not isinstance(ev.get("nome"), str) or not NOME_EVENTO.match(ev["nome"]):
        return None
    para = ev.get("para")
    if not (para in ("servidor", "todos") or (isinstance(para, str) and UID.match(para))):
        return None
    d = ev.get("dados")
    if isinstance(d, bool) or d is None:
        pass
    elif isinstance(d, (int, float)):
        d = _num(d, None)
    elif isinstance(d, str):
        d = d[:500]
    else:
        return None
    return {"para": para, "nome": ev["nome"], "dados": d}


class Passes:
    def __init__(self, segredo: str, validade_s: int = 8 * 3600):
        self.s = URLSafeTimedSerializer(segredo, salt="rolox-sala")
        self.validade = validade_s

    def criar(self, sala: str, user_id: str, nome: str, avatar: dict, parceiro: bool = False, dono: bool = False) -> str:
        return self.s.dumps({"s": sala, "u": user_id, "n": nome[:32], "a": avatar, "pc": bool(parceiro), "dn": bool(dono)})

    def ler(self, passe: str) -> Optional[dict]:
        try:
            d = self.s.loads(passe, max_age=self.validade)
        except (BadSignature, TypeError, ValueError):
            return None
        return d if isinstance(d, dict) and SALA_VALIDA.match(str(d.get("s", ""))) else None


def _num(v, padrao=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return padrao
    if not math.isfinite(f):
        return padrao
    return max(-LIMITE_COORD, min(LIMITE_COORD, f))


# gestos (emotes) que aparecem no balão em cima da cabeça: só estes, nada que o jogador escreva
EMOTES = {"acenar", "dancar", "comemorar", "rir", "triste", "bravo", "coracao", "pensar"}


def limpar_estado(d: dict) -> dict:
    """Só números finitos e limitados; nada que o jogador mande vira HTML ou código."""
    p = d.get("p") if isinstance(d.get("p"), list) else []
    p = (p + [0, 0, 0])[:3]
    em = d.get("em")
    return {"p": [round(_num(x), 3) for x in p], "r": round(_num(d.get("r")) % (2 * math.pi), 3),
            "m": bool(d.get("m")), "v": bool(d.get("v", True)), "em": em if isinstance(em, str) and em in EMOTES else None}


class Salas:
    def __init__(self, pasta: Optional[Path] = None):
        self._pasta = Path(pasta) if pasta else None

    @property
    def pasta(self) -> Path:
        p = self._pasta or Path(os.environ.get("ROLOX_PASTA_SALAS") or Path(tempfile.gettempdir()) / "rolox-salas")
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _arquivo(self, sala: str) -> Path:
        if not SALA_VALIDA.match(sala):
            raise ValueError("sala inválida")
        return self.pasta / f"{sala}.json"

    def _com_trava(self, sala: str, mudar):
        arq = self._arquivo(sala)
        with open(arq, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                try:
                    dados = json.loads(f.read() or "{}")
                except ValueError:
                    dados = {}
                resultado = mudar(dados)
                f.seek(0)
                f.truncate()
                f.write(json.dumps(dados, separators=(",", ":")))
                f.flush()                 # grava ANTES de destravar (senão outro processo lê a versão velha)
                return resultado
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def atualizar(self, passe: dict, estado: dict, agora: Optional[float] = None) -> list[dict]:
        """Compatível: só os OUTROS jogadores."""
        return self.trocar(passe, estado, agora)["jogadores"]

    def trocar(self, passe: dict, estado: dict, agora: Optional[float] = None) -> dict:
        """Grava o meu estado e devolve: outros jogadores, quem é o anfitrião, o que mudou no mundo
        desde a versão que eu tenho (mv) e as mensagens da Rede para mim."""
        agora = agora if agora is not None else time.time()
        eu = passe["u"]
        estado = estado if isinstance(estado, dict) else {}

        def mudar(dados):
            if not isinstance(dados.get("j"), dict):          # sala nova (ou formato antigo)
                dados.clear()
                dados.update({"j": {}, "mundo": {}, "v": 0, "caixas": {}})
            jog = dados["j"]
            for k in [k for k, v in jog.items() if agora - v.get("t", 0) > SUMIU_APOS]:
                jog.pop(k)
                dados["caixas"].pop(k, None)
            if not jog:                                       # sala vazia: o mundo começa de novo
                dados.update({"mundo": {}, "v": 0, "caixas": {}})
            fora = dados.setdefault("fora", {})
            for k in [k for k, ate in fora.items() if ate <= agora]:
                fora.pop(k)
            if eu in fora:                                    # expulso pelo dono: não volta para esta sala
                jog.pop(eu, None)
                return {"expulso": dados.get("motivos", {}).get(eu) or "Você foi expulso do servidor pelo dono.",
                        "jogadores": [], "anfitriao": None, "eu": eu, "mundo": [], "mv": 0, "eventos": []}
            if eu in jog or len(jog) < MAX_JOGADORES:
                jog[eu] = {"n": passe["n"], "a": passe.get("a") or {}, "pc": bool(passe.get("pc")), "dn": bool(passe.get("dn")),
                           **limpar_estado(estado), "t": agora, "e": jog.get(eu, {}).get("e", agora)}
            anfitriao = min(jog, key=lambda k: (jog[k]["e"], k)) if jog else None

            # mundo: só o anfitrião escreve
            if eu == anfitriao and isinstance(estado.get("mundo"), dict):
                _gravar_mundo(dados, estado["mundo"])
            # mensagens da Rede
            for ev in (estado.get("eventos") if isinstance(estado.get("eventos"), list) else [])[:MAX_EVENTOS]:
                ev = _evento_valido(ev)
                if not ev:
                    continue
                para = ev["para"]
                if para != "servidor" and eu != anfitriao:
                    continue                                   # só o anfitrião manda para os jogadores
                alvos = [anfitriao] if para == "servidor" else list(jog) if para == "todos" else [para]
                for alvo in alvos:
                    if alvo in jog:
                        caixa = dados["caixas"].setdefault(alvo, [])
                        if len(caixa) < MAX_CAIXA:
                            caixa.append({"de": eu, "nome": ev["nome"], "dados": ev["dados"],
                                          "para": "servidor" if para == "servidor" else "jogadores"})
            eventos = dados["caixas"].pop(eu, [])

            mundo, mv = [], dados["v"]
            if eu != anfitriao:
                try:
                    desde = int(estado.get("mv") or 0)
                except (TypeError, ValueError):
                    desde = 0
                if desde > dados["v"]:
                    desde = 0                                   # o mundo recomeçou
                novos = sorted(((k, it) for k, it in dados["mundo"].items() if it["v"] > desde), key=lambda x: x[1]["v"])
                if len(novos) > MAX_RESPOSTA_MUNDO:
                    novos = novos[:MAX_RESPOSTA_MUNDO]
                    mv = novos[-1][1]["v"]
                for k, it in novos:
                    mundo.append({"k": k, "x": 1} if it.get("x") else
                                 {"k": k, **({"c": it["c"], "p": it.get("p", "w")} if it.get("c") else {}),
                                  "props": it.get("props", {})})
            outros = [{"id": k, **{c: v.get(c) for c in ("n", "a", "p", "r", "m", "v", "pc", "dn", "em")}}
                      for k, v in jog.items() if k != eu]
            avisos = dados.setdefault("avisos", {}).pop(eu, [])
            return {"jogadores": outros, "anfitriao": anfitriao, "eu": eu, "mundo": mundo, "mv": mv,
                    "eventos": eventos, "avisos": avisos}
        return self._com_trava(passe["s"], mudar)

    # -------------------------------------------------------------- dono 👑💎
    def jogadores(self, sala: str) -> dict:
        """{user_id: nome} de quem está na sala agora."""
        def ver(dados):
            jog = dados.get("j") if isinstance(dados.get("j"), dict) else {}
            return {k: v.get("n", "?") for k, v in jog.items()}
        return self._com_trava(sala, ver)

    def eh_dono_na_sala(self, sala: str, user_id: str) -> bool:
        """A 👑 vem do passe assinado pelo site: o dono do ROLOX não pode ser expulso."""
        def ver(dados):
            jog = dados.get("j") if isinstance(dados.get("j"), dict) else {}
            return bool(jog.get(user_id, {}).get("dn"))
        return self._com_trava(sala, ver)

    def expulsar(self, sala: str, user_id: str, motivo: str = "", segundos: int = 600,
                 agora: Optional[float] = None) -> None:
        """Tira da sala e não deixa voltar por `segundos` (a pessoa vê o motivo e volta para Jogos)."""
        agora = agora if agora is not None else time.time()
        def mudar(dados):
            if not isinstance(dados.get("j"), dict):
                dados.update({"j": {}, "mundo": {}, "v": 0, "caixas": {}})
            dados["j"].pop(user_id, None)
            dados.setdefault("caixas", {}).pop(user_id, None)
            dados.setdefault("fora", {})[user_id] = agora + segundos
            dados.setdefault("motivos", {})[user_id] = (motivo or "Você foi expulso do servidor pelo dono.")[:200]
        self._com_trava(sala, mudar)

    def anunciar(self, sala: str, texto: str) -> int:
        """Aviso do dono para todo mundo da sala (aparece no meio da tela). Devolve quantos vão ver."""
        texto = str(texto or "").strip()[:200]
        def mudar(dados):
            jog = dados.get("j") if isinstance(dados.get("j"), dict) else {}
            caixas = dados.setdefault("avisos", {})
            for k in jog:
                lista = caixas.setdefault(k, [])
                if len(lista) < 5:
                    lista.append(texto)
            return len(jog)
        return self._com_trava(sala, mudar) if texto else 0

    def sair(self, passe: dict) -> None:
        def mudar(dados):
            if isinstance(dados.get("j"), dict):
                dados["j"].pop(passe["u"], None)
        self._com_trava(passe["s"], mudar)
