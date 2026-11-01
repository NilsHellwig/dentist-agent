import asyncio
import io
import os
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import mlx_whisper
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response
from mlx_whisper.audio import load_audio
from pydantic import BaseModel

MODELS = Path(__file__).parent / "models"
# reference clip + transcript for qwen-clone; created once with qwen-design
VOICE_DIR = Path(__file__).parent / "voice"

# TTS_ENGINE: qwen-clone (fixed voice cloned from voice/reference.wav), qwen-design (new voice from the description
# on every call, so it varies between sentences), qwen-serena (fixed speaker), piper
TTS_ENGINE = os.environ.get("TTS_ENGINE", "qwen-clone")
# Voice description for qwen-design; change freely
VOICE_DESCRIPTION = os.environ.get(
    "VOICE_DESCRIPTION",
    "Eine junge deutsche Frau mit warmer, freundlicher und lebhafter Stimme, klare Aussprache, "
    "natürlich und leicht lächelnd, wie eine sympathische Praxisassistentin am Telefon.",
)
PIPER_VOICE = os.environ.get("PIPER_VOICE", "ramona/low")  # <speaker>/<quality>

# Whisper invents phrases like "Vielen Dank." on silence/noise (no_speech_prob stays ~0).
# Hence: a loudness gate before recognition and a filter for known hallucinations as the sole result.
MIN_SPEECH_RMS = 0.01
HALLUCINATIONS = {"vielen dank", "danke", "vielen dank fürs zuschauen", "bis zum nächsten mal", "tschüss"}

# MLX streams are thread-bound: all model work runs in exactly one worker thread (which also serializes the GPU)
worker = ThreadPoolExecutor(max_workers=1)


async def in_worker(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(worker, fn, *args)


def _wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("int16")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


class PiperTTS:
    def __init__(self) -> None:
        from piper import PiperVoice

        speaker, quality = PIPER_VOICE.split("/")
        self.voice = PiperVoice.load(MODELS / f"piper/de/de_DE/{speaker}/{quality}/de_DE-{speaker}-{quality}.onnx")

    def synthesize(self, text: str) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            self.voice.synthesize_wav(text, wav)
        return buf.getvalue()


class QwenTTS:
    def __init__(self, design: bool) -> None:
        from mlx_audio.tts.utils import load_model

        self.design = design
        repo = "mlx-community/Qwen3-TTS-12Hz-1.7B-" + ("VoiceDesign-6bit" if design else "CustomVoice-8bit")
        self.model = load_model(repo)

    def synthesize(self, text: str) -> bytes:
        kwargs = (
            {"instruct": VOICE_DESCRIPTION}
            if self.design
            else {"voice": "serena", "instruct": "Freundlich, warm und lebhaft sprechen."}
        )
        chunks, rate = [], 24000
        for r in self.model.generate(text=text, lang_code="german", **kwargs):
            chunks.append(np.array(r.audio))
            rate = r.sample_rate
        return _wav_bytes(np.concatenate(chunks), rate)


class QwenCloneTTS:
    def __init__(self) -> None:
        from mlx_audio.tts.utils import load_model

        self.model = load_model("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit")
        self.ref_audio = str(VOICE_DIR / "reference.wav")
        self.ref_text = (VOICE_DIR / "reference.txt").read_text(encoding="utf-8").strip()

    def synthesize(self, text: str) -> bytes:
        chunks, rate = [], 24000
        for r in self.model.generate(text=text, lang_code="german", ref_audio=self.ref_audio, ref_text=self.ref_text):
            chunks.append(np.array(r.audio))
            rate = r.sample_rate
        return _wav_bytes(np.concatenate(chunks), rate)


def _load_tts():
    if TTS_ENGINE == "piper":
        return PiperTTS()
    if TTS_ENGINE == "qwen-clone":
        return QwenCloneTTS()
    return QwenTTS(design=TTS_ENGINE == "qwen-design")


def _normalize(text: str) -> str:
    return text.lower().strip(" .!?,")


def _is_silent(path: str) -> bool:
    samples = load_audio(path)  # 16 kHz mono float32 via ffmpeg
    frame = 480  # 30 ms
    n = len(samples) // frame
    if n == 0:
        return True
    rms = np.sqrt((samples[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    return float(np.percentile(rms, 95)) < MIN_SPEECH_RMS


def _transcribe(path: str) -> str:
    if _is_silent(path):
        return ""
    result = mlx_whisper.transcribe(
        path, path_or_hf_repo=str(MODELS / "whisper"), language="de", condition_on_previous_text=False
    )
    text = result["text"].strip()
    if _normalize(text) in HALLUCINATIONS or text.lower().startswith("untertitel"):
        return ""
    return text


tts_engine: PiperTTS | QwenTTS | QwenCloneTTS | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global tts_engine
    # Load models at startup and warm up once so the first call doesn't take 3-10 s extra
    tts_engine = await in_worker(_load_tts)
    await in_worker(tts_engine.synthesize, "Guten Tag.")
    yield


app = FastAPI(title="Voice Host", lifespan=lifespan)


class TTSRequest(BaseModel):
    text: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "tts": TTS_ENGINE}


@app.post("/stt")
async def stt(audio: UploadFile = File(...)) -> dict[str, str]:
    # ffmpeg decodes from a file, hence write to disk (webm/wav/m4a possible)
    with tempfile.NamedTemporaryFile(suffix=Path(audio.filename or "a.wav").suffix or ".wav") as tmp:
        tmp.write(await audio.read())
        tmp.flush()
        return {"text": await in_worker(_transcribe, tmp.name)}


@app.post("/tts")
async def tts(req: TTSRequest) -> Response:
    assert tts_engine is not None
    return Response(await in_worker(tts_engine.synthesize, req.text), media_type="audio/wav")
