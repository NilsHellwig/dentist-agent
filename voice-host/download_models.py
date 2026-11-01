from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = Path(__file__).parent / "models"
WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
PIPER_REPO = "rhasspy/piper-voices"
PIPER_VOICE = "de/de_DE/thorsten/high"

if __name__ == "__main__":
    print(snapshot_download(WHISPER_REPO, local_dir=MODELS / "whisper"))
    print(snapshot_download(PIPER_REPO, allow_patterns=[f"{PIPER_VOICE}/*"], local_dir=MODELS / "piper"))
