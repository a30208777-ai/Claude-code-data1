"""Sons e vídeos dos criadores: confere o arquivo de verdade (pelo começo dele, não pelo nome)
antes de mandar para o bucket "midias". Som até 5 MB, vídeo até 20 MB."""

from __future__ import annotations

import hashlib
from typing import Optional

MAX_SOM = 5 * 1024 * 1024
MAX_VIDEO = 20 * 1024 * 1024


def tipo_do_arquivo(dados: bytes) -> Optional[tuple[str, str, str]]:
    """(tipo, extensão, content-type) pela assinatura do arquivo, ou None se não for som/vídeo aceito."""
    c = dados[:16]
    if c[:3] == b"ID3" or (len(c) > 1 and c[0] == 0xFF and (c[1] & 0xE0) == 0xE0):
        return "som", "mp3", "audio/mpeg"
    if c[:4] == b"OggS":
        return "som", "ogg", "audio/ogg"
    if c[:4] == b"RIFF" and c[8:12] == b"WAVE":
        return "som", "wav", "audio/wav"
    if c[4:8] == b"ftyp":
        return "video", "mp4", "video/mp4"
    if c[:4] == b"\x1a\x45\xdf\xa3":
        return "video", "webm", "video/webm"
    return None


def preparar(dados: bytes, user_id: str) -> dict:
    """Confere e devolve {tipo, midia (caminho no bucket), content_type} ou levanta ValueError."""
    if not dados:
        raise ValueError("Arquivo vazio.")
    t = tipo_do_arquivo(dados)
    if not t:
        raise ValueError("Esse arquivo não é um som (mp3, ogg, wav) nem um vídeo (mp4, webm).")
    tipo, ext, ct = t
    if tipo == "som" and len(dados) > MAX_SOM:
        raise ValueError("Som grande demais (máximo 5 MB).")
    if len(dados) > MAX_VIDEO:
        raise ValueError("Vídeo grande demais (máximo 20 MB).")
    nome = hashlib.sha256(dados).hexdigest()[:16]
    return {"tipo": "video" if tipo == "video" else "som", "midia": f"{user_id}/{nome}.{ext}", "content_type": ct}
