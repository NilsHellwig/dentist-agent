#!/usr/bin/env bash
# Startet/stoppt alles: Voice-Host (uv-venv, GPU) auf dem Host, Postgres/Backend/Frontend in Docker.
# Nutzung: ./dev.sh start | stop | status | logs
set -euo pipefail
cd "$(dirname "$0")"

env_value() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }
RUN_DIR=".run"
PID_FILE="$RUN_DIR/voice-host.pid"
LOG_FILE="$RUN_DIR/voice-host.log"
VOICE_PORT=8001

voice_up() { curl -sf "http://127.0.0.1:$VOICE_PORT/health" >/dev/null 2>&1; }

start() {
  mkdir -p "$RUN_DIR"

  curl -sf http://127.0.0.1:11434/api/tags >/dev/null || { echo "Ollama läuft nicht. Bitte 'ollama serve' starten."; exit 1; }
  model="$(env_value LLM_MODEL)"
  ollama list | awk '{print $1}' | grep -qx "${model:-gemma4:e4b}" || { echo "Modell ${model:-gemma4:e4b} fehlt: ollama pull ${model:-gemma4:e4b}"; exit 1; }
  docker info >/dev/null 2>&1 || { echo "Docker läuft nicht. Bitte Docker Desktop starten."; exit 1; }
  [ -x voice-host/.venv/bin/python ] || { echo "Voice-Host-Umgebung fehlt: siehe README (uv venv + uv pip install)"; exit 1; }
  [ -d voice-host/models/whisper ] || { echo "Modelle fehlen: voice-host/.venv/bin/python voice-host/download_models.py"; exit 1; }

  if voice_up; then
    echo "Voice-Host läuft bereits."
  else
    py="$PWD/voice-host/.venv/bin/python"
    echo "Starte Voice-Host (Modelle laden, das dauert beim ersten Mal)…"
    cd voice-host
    nohup "$py" -m uvicorn server:app --host 127.0.0.1 --port "$VOICE_PORT" >"../$LOG_FILE" 2>&1 </dev/null &
    echo $! >"../$PID_FILE"
    cd ..
    for _ in $(seq 1 180); do voice_up && break; sleep 1; done
    voice_up || { echo "Voice-Host startet nicht. Siehe $LOG_FILE"; exit 1; }
  fi

  docker compose up -d --build
  echo
  echo "Bereit:  http://localhost:3000"
  echo "Stimme:  $(curl -s http://127.0.0.1:$VOICE_PORT/health)"
}

stop() {
  docker compose down
  if [ -f "$PID_FILE" ]; then kill "$(cat "$PID_FILE")" 2>/dev/null || true; rm -f "$PID_FILE"; fi
  pkill -f "uvicorn server:app --host 127.0.0.1 --port $VOICE_PORT" 2>/dev/null || true
  echo "Gestoppt."
}

status() {
  voice_up && echo "voice-host: läuft ($(curl -s http://127.0.0.1:$VOICE_PORT/health))" || echo "voice-host: aus"
  docker compose ps
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  logs) tail -n 50 -f "$LOG_FILE" ;;
  *) echo "Nutzung: $0 start|stop|status|logs"; exit 1 ;;
esac
