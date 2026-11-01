import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic_ai.messages import AgentStreamEvent, FunctionToolCallEvent, FunctionToolResultEvent
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import admin, voice
from app.agent import agent
from app.config import settings
from app.db.seed import init_db
from app.deps import CallEnded, CallSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def warm_up() -> None:
    """Preload the LLM and greeting audio so the first call doesn't pay the load time."""
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
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


GREETING = "Guten Tag, hier ist die Zahnarztpraxis Nordlicht. Wie kann ich Ihnen helfen?"
FAREWELL = "Vielen Dank für Ihren Anruf. Auf Wiederhören!"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
IDLE_TIMEOUT_S = 300
AGENT_TIMEOUT_S = 60
EMPTY_REPLY = "Das habe ich leider nicht verstanden. Können Sie das bitte wiederholen?"


TOOL_RESULT_MAX_CHARS = 500


async def send_tool_events(ws: WebSocket, events: AsyncIterable[AgentStreamEvent]) -> None:
    """Mirrors tool calls and their results to the call UI as they happen."""
    async for event in events:
        if isinstance(event, FunctionToolCallEvent):
            try:
                args = event.part.args_as_dict()
            except ValueError:
                args = {"raw": str(event.part.args)}
            await ws.send_json({"type": "tool_call", "id": event.tool_call_id, "name": event.part.tool_name, "args": args})
        elif isinstance(event, FunctionToolResultEvent):
            result = event.part.model_response_str() if hasattr(event.part, "model_response_str") else str(event.part.content)
            await ws.send_json({"type": "tool_result", "id": event.tool_call_id, "result": result[:TOOL_RESULT_MAX_CHARS]})


async def speak(ws: WebSocket, text: str) -> None:
    await ws.send_json({"type": "agent_text", "text": text})
    # Sentence by sentence: the customer hears sentence 1 while sentence 2 is still being synthesized
    for sentence in voice.split_sentences(text):
        await ws.send_bytes(await voice.synthesize(sentence))


@app.websocket("/ws/call")
async def call(ws: WebSocket) -> None:
    """Protocol: client sends audio as a binary frame (one utterance) or {"type":"hangup"}.

    Per turn the server sends: user_text, any tool_call/tool_result pairs, agent_text (full text),
    then one binary frame (WAV) per sentence, then turn_done.
    After end_call or hangup, {"type":"ended"} follows and the server closes.
    """
    # CORS doesn't apply to WebSockets, so check the origin ourselves
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
                break  # customer went silent: end the call
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
            session.turn += 1
            reply = FAREWELL
            try:
                async with asyncio.timeout(AGENT_TIMEOUT_S):
                    result = await agent.run(
                        text,
                        deps=session,
                        message_history=history,
                        event_stream_handler=lambda _ctx, events: send_tool_events(ws, events),
                    )
                history = result.all_messages()
                reply = result.output.strip() or EMPTY_REPLY
            except CallEnded:
                pass  # fixed farewell; the small model often phrases it awkwardly
            logger.info("Turn: stt=%.1fs llm=%.1fs", t_stt, time.perf_counter() - t0 - t_stt)
            await speak(ws, reply)
            await ws.send_json({"type": "turn_done"})
        await ws.send_json({"type": "ended"})
        await ws.close()
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Error during call")
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "text": "Technischer Fehler. Bitte versuchen Sie es erneut."})
            await ws.close(code=1011)
