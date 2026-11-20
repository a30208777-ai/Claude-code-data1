"""IA do ROLOX Studio (no site): ajuda a criar jogos e scripts.

Usa a mesma ideia do IA/chat_ias.py: uma lista de modelos (do melhor para o mais
simples) e, se um falhar ou bater limite, tenta o próximo. As chaves NUNCA vão para o
navegador: ficam nas variáveis do servidor (CHAVE_AION, CHAVE_GEMINI, ...). Sem
chave, só os provedores gratuitos sem chave entram (Kilo, LLM7, OVH).

Cada mensagem custa 10 tickets (o site cobra antes e devolve se nenhuma IA responder).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

CUSTO_TICKETS = 10
MAX_MENSAGENS = 12          # histórico que vai para a IA
MAX_CARACTERES = 2000       # por mensagem
PRAZO_TOTAL_S = 45          # o gunicorn derruba em 60 s
PRAZO_MODELO_S = 12

log = logging.getLogger("rolox.ia")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

AION_URL = "https://api.aionlabs.ai/v1/chat/completions"
COHERE_URL = "https://api.cohere.ai/compatibility/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
ZAI_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GONKA_URL = "https://proxy.gonkabroker.com/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
KILO_URL = "https://api.kilo.ai/api/gateway/chat/completions"
LLM7_URL = "https://api.llm7.io/v1/chat/completions"
MODELSCOPE_URL = "https://api-inference.modelscope.cn/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OVH_URL = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
SILICONFLOW_URL = "https://api.siliconflow.cn/v1/chat/completions"

# (modelo, url, variável da chave ou None = sem chave). Mesma ordem do chat_ias.py.
_LISTA = [
    ("aion-labs/aion-3.0", AION_URL, "CHAVE_AION"),
    ("aion-labs/aion-2.0", AION_URL, "CHAVE_AION"),
    ("command-a-03-2025", COHERE_URL, "CHAVE_COHERE"),
    ("command-r-plus-08-2024", COHERE_URL, "CHAVE_COHERE"),
    ("gemini-3.8-flash", GEMINI_URL, "CHAVE_GEMINI"),
    ("gemini-3.6-flash", GEMINI_URL, "CHAVE_GEMINI"),
    ("gemini-2.5-flash", GEMINI_URL, "CHAVE_GEMINI"),
    ("mistral-medium-latest", MISTRAL_URL, "CHAVE_MISTRAL"),
    ("codestral-latest", MISTRAL_URL, "CHAVE_MISTRAL"),
    ("mistral-small-latest", MISTRAL_URL, "CHAVE_MISTRAL"),
    ("glm-4.7-flash", ZAI_URL, "CHAVE_ZAI"),
    ("deepseek-ai/DeepSeek-V4-Flash-0731", GONKA_URL, "CHAVE_GONKA"),
    ("openai/gpt-oss-120b", GROQ_URL, "CHAVE_GROQ"),
    ("openai/gpt-oss-20b", GROQ_URL, "CHAVE_GROQ"),
    ("nvidia/nemotron-3-ultra-550b-a55b:free", KILO_URL, None),
    ("poolside/laguna-s-2.1:free", KILO_URL, None),
    ("cohere/north-mini-code:free", KILO_URL, None),
    ("openrouter/free", KILO_URL, None),
    ("kilo-auto/free", KILO_URL, None),
    ("minimax-m2.7", LLM7_URL, None),
    ("gpt-oss:20b", LLM7_URL, None),
    ("Qwen/Qwen3.5-35B-A3B", MODELSCOPE_URL, "CHAVE_MODELSCOPE"),
    ("nvidia/nemotron-3-ultra-550b-a55b", NVIDIA_URL, "CHAVE_NVIDIA"),
    ("google/gemma-4-31b-it:free", OPENROUTER_URL, "CHAVE_OPENROUTER"),
    ("cohere/north-mini-code:free", OPENROUTER_URL, "CHAVE_OPENROUTER"),
    ("gpt-oss-120b", OVH_URL, None),
    ("Qwen3.8-27B", OVH_URL, None),
    ("gpt-oss-20b", OVH_URL, None),
    ("XingChenAGI/Xing4.0-29B", SILICONFLOW_URL, "CHAVE_SILICONFLOW"),
]


def modelos() -> list[tuple[str, str, Optional[str]]]:
    """Modelos disponíveis agora: sem chave sempre; com chave só se a variável existir."""
    lista = []
    for nome, url, var in _LISTA:
        if var is None:
            lista.append((nome, url, None))
        elif os.environ.get(var, "").strip():
            lista.append((nome, url, os.environ[var].strip()))
    return lista


INSTRUCAO = """Você é a IA do ROLOX Studio, um editor de jogos 3D da comunidade ROLOX. Responda em português do Brasil,
curto e direto, com exemplos de código prontos para colar. Regras do ROLOX Studio:
- LocalScript roda no aparelho e é em Lua/Luau. Script (servidor) é em Python. ModuleScript pode ser Lua ou Python.
  A linguagem pode ser trocada com a linha: _++linguagemprogroma++_ = lua  (ou python)
- Acesso: game, workspace, game:GetService("Players"), game.Players.LocalPlayer, Instance.new("Part", workspace),
  Vector3.new(x, y, z), Color3.fromRGB(r, g, b), peca.Touched:Connect(funcao), RunService.Heartbeat:Connect(funcao(dt)),
  wait(segundos), task.delay(s, funcao), Humanoid.Health, Humanoid.Died, HumanoidRootPart.Position.
- Em Python: workspace.Peca.Touched.Connect(funcao), Instance.new("Part", workspace), Vector3.new(...), async def + await wait(s).
- Peças: Part, SpawnLocation, MeshPart, Model, Folder; propriedades Position, Size, Color, Anchored, CanCollide,
  Transparency, Shape ("Block", "Ball", "Cylinder").
- Placar: crie a pasta "leaderstats" dentro do jogador com IntValue/NumberValue; o 1º valor vira recorde no site.
- Multijogador (modelo ANFITRIÃO do ROLOX): os Scripts rodam no aparelho de UM jogador (o anfitrião) e o que eles mudam
  nas peças (posição, cor, transparência, colisão, peças criadas/apagadas) aparece para todos. LocalScripts rodam em cada um.
  Mensagens: LocalScript -> game:GetService("Rede"):ParaServidor("nome", dados)
             Script -> Rede.Recebido:Connect(function(jogador, nome, dados) ... end)
             Script -> Rede:ParaTodos("nome", dados) / Rede:ParaJogador(jogador, "nome", dados)
             LocalScript -> Rede.RecebidoDoServidor:Connect(function(nome, dados) ... end)
  dados: texto, número ou true/false. Coisas que todos devem ver (porta, placar) ficam no Script.
- Cofre (progresso do jogador que fica salvo neste jogo): local c = game:GetService("Cofre")
  c:Ler("moedas", 0), c:Salvar("moedas", 10), c:Somar("vitorias", 1). Use no LocalScript (são dados do próprio jogador).
- Para publicar: botão "🚀 Enviar ao ROLOX" (o dono testa e aprova antes de aparecer em Jogos).
Nunca peça senha, token ou dados pessoais. Não ajude a trapacear, hackear contas ou atacar outros jogadores.

VOCÊ MESMA FAZ AS MUDANÇAS NO MAPA. Não mande o usuário criar peça nem colar código: faça você, com um bloco
```acoes
[ ...lista de ações em JSON... ]
```
Ações (JSON válido, aspas duplas, no máximo 60):
- {"acao": "criar", "classe": "Part"|"SpawnLocation"|"Model"|"Folder"|"IntValue"|"NumberValue"|"Script"|"LocalScript"|"ModuleScript",
   "nome": "Porta", "pai": "Workspace" (ou "StarterPlayerScripts", "ServerScriptService", "ReplicatedStorage", "Workspace.Casa"),
   "posicao": [x, y, z], "tamanho": [x, y, z], "rotacao": [x, y, z], "cor": "#rrggbb", "ancorada": true, "colide": true,
   "transparencia": 0..1, "forma": "Block"|"Ball"|"Cylinder", "valor": 0,
   "linguagem": "lua"|"python", "codigo": "o código do script (\n para quebrar linha)"}
  Se já existir algo com o mesmo nome no mesmo lugar, ele é atualizado (não duplica).
- {"acao": "editar", "alvo": "Workspace.Porta", ...as mesmas propriedades...}
- {"acao": "apagar", "alvo": "Workspace.Porta"}   (o usuário confirma antes)
Regras: olhe o MAPA ATUAL abaixo; se o que o script precisa não existe (ex.: a porta), CRIE antes no mesmo bloco.
O chão fica em y=0; uma peça de altura h em cima do chão fica em y = h/2. Peças novas já vêm ancoradas.
Em Touched, SEMPRE confira se quem tocou é um jogador (senão o chão ou outra peça disparam o evento):
  Lua:    if outro.Parent and outro.Parent:FindFirstChildOfClass("Humanoid") then ... end
  Python: if outro.Parent and outro.Parent.FindFirstChildOfClass("Humanoid"): ...
LocalScript (Lua) vai em StarterPlayerScripts; Script (Python) vai em ServerScriptService.
Depois do bloco, explique em 1 a 3 frases o que você fez e como testar (botão ▶ Jogar)."""


def limpar_historico(mensagens) -> list[dict]:
    """Só user/assistant, texto, tamanho limitado, últimas N."""
    saida = []
    for m in mensagens if isinstance(mensagens, list) else []:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        texto = str(m.get("content", "")).strip()[:MAX_CARACTERES]
        if texto:
            saida.append({"role": m["role"], "content": texto})
    saida = saida[-MAX_MENSAGENS:]
    while saida and saida[0]["role"] != "user":
        saida.pop(0)
    return saida


MAX_CENA = 6000


def perguntar(mensagens: list[dict], http=requests, agora=time.monotonic,
              cena: str = "") -> tuple[Optional[str], Optional[str]]:
    """Tenta os modelos em ordem até um responder. Devolve (modelo, texto) ou (None, None)."""
    sistema = INSTRUCAO
    if cena:
        sistema += "\n\nMAPA ATUAL (nome [classe] pos tam):\n" + str(cena)[:MAX_CENA]
    historico = [{"role": "system", "content": sistema}] + mensagens
    fim = agora() + PRAZO_TOTAL_S
    for nome, url, chave in modelos():
        resta = fim - agora()
        if resta < 3:
            break
        cab = {"Content-Type": "application/json"}
        if chave:
            cab["Authorization"] = f"Bearer {chave}"
        inicio = agora()
        try:
            r = http.post(url, headers=cab, json={"model": nome, "messages": historico, "max_tokens": 1200},
                          timeout=min(PRAZO_MODELO_S, resta))
        except requests.RequestException as e:
            log.info("IA %s: falhou (%s) em %.1fs", nome, type(e).__name__, agora() - inicio)
            continue
        if r.status_code != 200:
            # limite ou erro: próximo modelo (registra só o código e o começo do erro, nada do usuário)
            log.info("IA %s: HTTP %s em %.1fs %s", nome, r.status_code, agora() - inicio,
                     str(getattr(r, "text", ""))[:160].replace("\n", " "))
            continue
        try:
            msg = r.json()["choices"][0]["message"]
            texto = msg.get("content") or ""
        except (KeyError, IndexError, ValueError, TypeError, AttributeError):
            log.info("IA %s: resposta em formato inesperado", nome)
            continue
        if isinstance(texto, str) and texto.strip():
            log.info("IA %s: respondeu em %.1fs", nome, agora() - inicio)
            return nome, texto.strip()[:8000]
        log.info("IA %s: resposta vazia", nome)
    log.info("IA: nenhum modelo respondeu (%d tentados)", len(modelos()))
    return None, None
