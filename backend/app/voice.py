import re
from collections import OrderedDict

import httpx

from app.config import settings

_client = httpx.AsyncClient(base_url=settings.voice_host_url, timeout=60)
_cache: OrderedDict[str, bytes] = OrderedDict()
_CACHE_SIZE = 64


def split_sentences(text: str) -> list[str]:
    """Teilt an Satzenden, damit der erste Satz schon spielt, während der nächste synthetisiert wird."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts or [text.strip()]


async def transcribe(audio: bytes) -> str:
    resp = await _client.post("/stt", files={"audio": ("audio.webm", audio)})
    resp.raise_for_status()
    return resp.json()["text"]


async def synthesize(text: str) -> bytes:
    # Wiederkehrende Sätze (Begrüßung, Abschied, Standardfragen) nicht erneut synthetisieren
    if text in _cache:
        _cache.move_to_end(text)
        return _cache[text]
    resp = await _client.post("/tts", json={"text": text})
    resp.raise_for_status()
    _cache[text] = resp.content
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return resp.content
