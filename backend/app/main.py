import asyncio
import contextlib
import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import voice
from app.agent import agent
from app.config import settings
from app.db.seed import init_db
from app.deps import CallEnded, CallSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def warm_up() -> None:
    """LLM und Begrüßungs-Audio vorladen; der erste Anruf soll nicht die Ladezeit bezahlen."""
    ollama_root = settings.ollama_base_url.removesuffix("/v1")
    with contextlib.suppress(Exception):
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(f"{ollama_root}/api/generate", json={"model": settings.llm_model, "keep_alive": "30m"})
    for text in (GREETING, FAREWELL):
        with contextlib.suppress(Exception):
            await voice.synthesize(text)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    task = asyncio.create_task(warm_up())
    yield
    task.cancel()


app = FastAPI(title="Praxis Voice Agent", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


GREETING = "Guten Tag, hier ist die Zahnarztpraxis Nordlicht. Wie kann ich Ihnen helfen?"
FAREWELL = "Vielen Dank für Ihren Anruf. Auf Wiederhören!"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
IDLE_TIMEOUT_S = 300
AGENT_TIMEOUT_S = 60
EMPTY_REPLY = "Das habe ich leider nicht verstanden. Können Sie das bitte wiederholen?"


async def speak(ws: WebSocket, text: str) -> None:
    await ws.send_json({"type": "agent_text", "text": text})
    # Satz für Satz: der Kunde hört Satz 1, während Satz 2 noch synthetisiert wird
    for sentence in voice.split_sentences(text):
        await ws.send_bytes(await voice.synthesize(sentence))


@app.websocket("/ws/call")
async def call(ws: WebSocket) -> None:
    """Protokoll: Client sendet Audio als Binary-Frame (eine Äußerung) oder {"type":"hangup"}.

    Server sendet je Zug: user_text, agent_text (ganzer Text), dann je Satz ein Binary-Frame (WAV), dann turn_done.
    Nach end_call oder hangup folgt {"type":"ended"} und der Server schließt.
    """
    # CORS gilt nicht für WebSockets, daher Origin selbst prüfen
    if ws.headers.get("origin") not in settings.cors_origin_list:
        await ws.close(code=1008)
        return
    await ws.accept()
    session, history = CallSession(), []
    try:
        await speak(ws, GREETING)
        await ws.send_json({"type": "turn_done"})
        while not session.ended:
            try:
                msg = await asyncio.wait_for(ws.receive(), IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                break  # Kunde ist still geworden: Gespräch beenden
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("text") is not None:
                if json.loads(msg["text"]).get("type") == "hangup":
                    break
                continue
            audio = msg.get("bytes") or b""
            if not audio or len(audio) > MAX_AUDIO_BYTES:
                await ws.send_json({"type": "turn_done"})
                continue
            t0 = time.perf_counter()
            text = await voice.transcribe(audio)
            t_stt = time.perf_counter() - t0
            if not text:
                await ws.send_json({"type": "turn_done"})
                continue
            await ws.send_json({"type": "user_text", "text": text})
            reply = FAREWELL
            try:
                async with asyncio.timeout(AGENT_TIMEOUT_S):
                    result = await agent.run(text, deps=session, message_history=history)
                history = result.all_messages()
                reply = result.output.strip() or EMPTY_REPLY
            except CallEnded:
                pass  # fester Abschiedssatz; das kleine Modell formuliert ihn oft unpassend
            logger.info("Zug: stt=%.1fs llm=%.1fs", t_stt, time.perf_counter() - t0 - t_stt)
            await speak(ws, reply)
            await ws.send_json({"type": "turn_done"})
        await ws.send_json({"type": "ended"})
        await ws.close()
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Fehler im Gespräch")
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "text": "Technischer Fehler. Bitte versuchen Sie es erneut."})
            await ws.close(code=1011)
