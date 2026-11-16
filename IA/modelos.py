"""Lista de modelos e chamada com troca automática (mesma ideia do chat_ias.py).

Separado do chat_ias.py para poder ser importado pelos jogos sem perguntar
a pasta da IA nem carregar os comandos de arquivo.

As chaves vêm das mesmas variáveis de ambiente do chat_ias.py (CHAVE_AION,
CHAVE_GEMINI, ...). Nunca coloque chaves dentro do app do jogador: este módulo
roda no servidor (PC host, servidor de jogo ou Termux).
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional

import requests

# Modelo = (nome, url, chave). Chave None = provedor anônimo (sem chave).
Modelo = tuple[str, str, Optional[str]]


def _chave(nome_env: str) -> str:
    return os.getenv(nome_env, "")


def _provedor(url: str, chave: Optional[str], nomes: list[str]) -> list[Modelo]:
    return [(n, url, chave) for n in nomes]


def carregar_modelos() -> list[Modelo]:
    """Monta a lista do melhor para o mais simples, igual ao chat_ias.py."""
    m: list[Modelo] = []
    m += _provedor("https://api.aionlabs.ai/v1/chat/completions", _chave("CHAVE_AION"), [
        "aion-labs/aion-3.0", "aion-labs/aion-2.0", "aion-labs/aion-3.0-mini",
        "aion-labs/aion-rp-llama-3.1-8b",
    ])
    m += _provedor("https://api.cohere.ai/compatibility/v1/chat/completions", _chave("CHAVE_COHERE"), [
        "command-a-reasoning-08-2025", "command-a-03-2025", "command-r-plus-08-2024",
        "command-a-vision-07-2025", "command-r-08-2024", "command-r7b-12-2024",
        "command-a-translate-08-2025", "command-r7b-arabic-02-2025",
        "c4ai-aya-expanse-32b", "c4ai-aya-vision-32b",
    ])
    m += _provedor("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   _chave("CHAVE_GEMINI"), [
        "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
        "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-4-31b-it", "gemma-4-26b-a4b-it",
    ])
    m += _provedor("https://api.mistral.ai/v1/chat/completions", _chave("CHAVE_MISTRAL"), [
        "mistral-medium-latest", "mistral-large-latest", "mistral-small-latest",
        "codestral-latest", "ministral-8b-latest", "ministral-3b-latest",
    ])
    m += _provedor("https://open.bigmodel.cn/api/paas/v4/chat/completions", _chave("CHAVE_ZAI"), [
        "glm-4.7-flash", "glm-4.6v-flash", "glm-4.5-flash",
    ])
    m += _provedor("https://proxy.gonkabroker.com/v1/chat/completions", _chave("CHAVE_GONKA"), [
        "MiniMaxAI/MiniMax-M2.7", "deepseek-ai/DeepSeek-V4-Flash-0731", "zai-org/GLM-5.3-Flash",
    ])
    m += _provedor("https://api.groq.com/openai/v1/chat/completions", _chave("CHAVE_GROQ"), [
        "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b",
    ])
    m += _provedor("https://api.kilo.ai/api/gateway/chat/completions", None, [
        "nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "poolside/laguna-s-2.1:free", "poolside/laguna-xs-2.1:free", "cohere/north-mini-code:free",
        "openrouter/free", "nvidia/nemotron-3.5-lightning:free", "liquid/lfm-2.5-2.6b:free",
        "kilo-auto/free", "dots-studio/dots-3-note-preview:free", "recursive/flint-v1.0:free",
        "xingchen-agi/xing4.0-29b-a4b:free", "nvidia/nemotron-3.5-super-vl:free",
        "reflection/beam-free", "stealth/glyph-cluster",
    ])
    m += _provedor("https://api.llm7.io/v1/chat/completions", None, [
        "minimax-m2.7", "gpt-oss:20b", "nemotron-3-nano:30b", "mistral-Nemo-Instruct-2407",
    ])
    m += _provedor("https://api-inference.modelscope.cn/v1/chat/completions", _chave("CHAVE_MODELSCOPE"), [
        "Qwen/Qwen3.5-35B-A3B", "Qwen/Qwen3.5-27B",
    ])
    m += _provedor("https://integrate.api.nvidia.com/v1/chat/completions", _chave("CHAVE_NVIDIA"), [
        "nvidia/nemotron-3-ultra-550b-a55b", "openai/gpt-oss-20b", "google/gemma-4-31b-it",
    ])
    m += _provedor("https://openrouter.ai/api/v1/chat/completions", _chave("CHAVE_OPENROUTER"), [
        "google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free", "cohere/north-mini-code:free",
        "poolside/laguna-s-2.1:free", "poolside/laguna-xs-2.1:free",
        "dots-studio/dots-3-note-preview:free", "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3.5-lightning:free", "thinkingmachines/inkling:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free", "recursive/flint-v1.0:free",
        "xingchen-agi/xing4.0-29b-a4b:free", "nvidia/nemotron-3.5-super-vl:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "thinkingmachines/inkling-small:free",
    ])
    m += _provedor("https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions", None, [
        "gpt-oss-120b", "gpt-oss-20b", "Qwen3.5-397B-A17B", "Qwen3.6-27B", "Qwen3.8-27B",
        "Qwen3.5-9B", "Mistral-Nemo-Instruct-2407",
    ])
    m += _provedor("https://api.siliconflow.cn/v1/chat/completions", _chave("CHAVE_SILICONFLOW"), [
        "tencent/Hunyuan-MT-7B", "XingChenAGI/Xing4.0-29B",
    ])
    # Filtro no FINAL (no chat_ias.py ele fica no meio da lista, então ModelScope,
    # NVIDIA, OpenRouter e SiliconFlow sem chave eram chamados e davam erro 401).
    return [x for x in m if x[2] is None or x[2]]


# ---------------------------------------------------------------- chamadas
Chamador = Callable[[str, str, Optional[str], list, float], tuple[Optional[str], Optional[str]]]


def limite_atingido(resp: requests.Response) -> bool:
    if resp.status_code in (429, 402):
        return True
    if resp.status_code == 403:
        return any(p in resp.text.lower() for p in ("quota", "rate limit", "exceeded"))
    return False


def chamar_modelo(nome: str, url: str, chave: Optional[str], mensagens: list,
                  timeout: float) -> tuple[Optional[str], Optional[str]]:
    """Retorna (texto, None) ou (None, motivo). Motivo começa com 'limite' se for cota."""
    cab = {"Content-Type": "application/json"}
    if chave:
        cab["Authorization"] = f"Bearer {chave}"
    try:
        r = requests.post(url, headers=cab, timeout=timeout,
                          json={"model": nome, "messages": mensagens, "max_tokens": 300})
    except requests.Timeout as e:
        return None, f"conexão: demorou demais ({e.__class__.__name__})"
    except requests.ConnectionError as e:
        # o endereço inteiro está fora do ar: não adianta tentar os outros modelos dele
        return None, f"provedor fora: {e.__class__.__name__}"
    except requests.RequestException as e:
        return None, f"conexão: {e.__class__.__name__}"
    if r.status_code == 200:
        try:
            texto = r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError):
            return None, "resposta inesperada"
        if not texto or not str(texto).strip():
            return None, "resposta vazia"
        return str(texto), None
    if limite_atingido(r):
        return None, f"limite HTTP {r.status_code}"
    return None, f"erro HTTP {r.status_code}"


class Roteador:
    """Percorre os modelos até um responder, com dois cuidados para jogos:

    * prazo total (`prazo`): o jogador não pode ficar esperando 1 minuto;
    * pausa (`pausa_limite`): modelo que bateu limite fica de fora por um tempo,
      em vez de ser tentado de novo a cada fala.
    """

    def __init__(self, modelos: Optional[list[Modelo]] = None, *, prazo: float = 12.0,
                 timeout_por_modelo: float = 8.0, pausa_limite: float = 120.0,
                 pausa_erro: float = 30.0, chamador: Chamador = chamar_modelo,
                 relogio: Callable[[], float] = time.monotonic):
        self.modelos = modelos if modelos is not None else carregar_modelos()
        self.prazo = prazo
        self.timeout_por_modelo = timeout_por_modelo
        self.pausa_limite = pausa_limite
        self.pausa_erro = pausa_erro
        self.chamador = chamador
        self.relogio = relogio
        self.preferido: Optional[str] = None
        self._pausados: dict[tuple[str, str], float] = {}

    def em_ordem(self) -> list[Modelo]:
        agora = self.relogio()
        livres = [m for m in self.modelos if self._pausados.get((m[0], m[1]), 0) <= agora]
        if self.preferido:
            livres.sort(key=lambda m: m[0] != self.preferido)
        return livres

    def perguntar(self, mensagens: list) -> tuple[Optional[str], Optional[str]]:
        """Devolve (nome_do_modelo, texto) ou (None, None) se nenhum respondeu a tempo."""
        inicio = self.relogio()
        for nome, url, chave in self.em_ordem():
            if self._pausados.get((nome, url), 0) > self.relogio():
                continue                      # pausado durante esta mesma fala
            restante = self.prazo - (self.relogio() - inicio)
            if restante <= 0.5:
                break
            texto, erro = self.chamador(nome, url, chave, mensagens,
                                        min(self.timeout_por_modelo, restante))
            if texto is not None:
                return nome, texto
            pausa = self.pausa_limite if erro and erro.startswith("limite") else self.pausa_erro
            ate = self.relogio() + pausa
            if erro and erro.startswith("provedor fora"):
                for n, u, _ in self.modelos:
                    if u == url:
                        self._pausados[(n, u)] = ate
            else:
                self._pausados[(nome, url)] = ate
        return None, None
