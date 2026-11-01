"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/call";
const MIN_RECORDING_MS = 400;
const FAREWELL_PAUSE_MS = 1800;

export type Phase = "idle" | "connecting" | "live" | "closing";
export type Status = "thinking" | "speaking" | "ready" | "listening";
export type Line = { role: "user" | "agent"; text: string };

function pickMimeType(): string | undefined {
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
}

export function useCall() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [status, setStatus] = useState<Status>("thinking");
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);

  const ws = useRef<WebSocket | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordingStart = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);
  const playing = useRef(false);
  const queue = useRef<Blob[]>([]);
  const discard = useRef(false);
  const turnDone = useRef(false);
  const ended = useRef(false);

  const reset = useCallback(() => {
    audio.current?.pause();
    audio.current = null;
    queue.current = [];
    playing.current = false;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    recorder.current = null;
    const socket = ws.current;
    ws.current = null;
    socket?.close();
    setPhase("idle");
  }, []);

  // After audio ends and turn_done: either next turn or end the call
  const settle = useCallback(() => {
    if (playing.current || !turnDone.current) return;
    if (ended.current) {
      setPhase("closing");
      setTimeout(reset, FAREWELL_PAUSE_MS);
    } else {
      setStatus("ready");
    }
  }, [reset]);

  // Replies arrive sentence by sentence as separate clips; they are played in order
  const playNext = useCallback(() => {
    const data = queue.current.shift();
    if (!data) {
      audio.current = null;
      playing.current = false;
      settle();
      return;
    }
    const el = new Audio(URL.createObjectURL(data));
    audio.current = el;
    playing.current = true;
    setStatus("speaking");
    const done = () => {
      URL.revokeObjectURL(el.src);
      if (audio.current === el) playNext();
    };
    el.onended = done;
    el.onerror = done;
    el.play().catch(done);
  }, [settle]);

  // Abort current playback; clips of the same reply that still arrive are discarded
  const stopAudio = useCallback(() => {
    const el = audio.current;
    audio.current = null;
    el?.pause();
    queue.current = [];
    playing.current = false;
    discard.current = !turnDone.current;
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setLines([]);
    setPhase("connecting");
    turnDone.current = false;
    ended.current = false;
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Mikrofonzugriff nicht erlaubt. Bitte in den Browser-Einstellungen freigeben.");
      setPhase("idle");
      return;
    }
    const socket = new WebSocket(WS_URL);
    ws.current = socket;
    socket.binaryType = "blob";
    socket.onopen = () => {
      setPhase("live");
      setStatus("thinking");
    };
    socket.onmessage = (event) => {
      if (event.data instanceof Blob) {
        if (discard.current) return;
        queue.current.push(event.data);
        if (!playing.current) playNext();
        return;
      }
      const msg = JSON.parse(event.data as string);
      if (msg.type === "user_text") setLines((l) => [...l, { role: "user", text: msg.text }]);
      else if (msg.type === "agent_text") {
        turnDone.current = false;
        setLines((l) => [...l, { role: "agent", text: msg.text }]);
      } else if (msg.type === "turn_done") {
        turnDone.current = true;
        discard.current = false;
        settle();
      } else if (msg.type === "ended") {
        ended.current = true;
        settle();
      } else if (msg.type === "error") {
        setError(msg.text);
        reset();
      }
    };
    socket.onclose = () => {
      if (ws.current !== socket) return; // closed by ourselves
      // Server closed after "ended": the farewell runs via settle()
      if (!ended.current) {
        setError((e) => e ?? "Verbindung zum Server verloren.");
        reset();
      }
    };
    socket.onerror = () => setError("Server nicht erreichbar.");
  }, [playNext, reset, settle]);

  const startTalking = useCallback(() => {
    if (!stream.current || ws.current?.readyState !== WebSocket.OPEN) return;
    if (status !== "ready" && status !== "speaking") return;
    // Interrupting is allowed: stop current playback
    stopAudio();
    const rec = new MediaRecorder(stream.current, { mimeType: pickMimeType() });
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      const tooShort = Date.now() - recordingStart.current < MIN_RECORDING_MS;
      if (tooShort || ws.current?.readyState !== WebSocket.OPEN) return setStatus("ready");
      ws.current.send(new Blob(chunks, { type: rec.mimeType }));
      setStatus("thinking");
    };
    recorder.current = rec;
    recordingStart.current = Date.now();
    rec.start();
    setStatus("listening");
  }, [status, stopAudio]);

  const stopTalking = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const hangUp = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      stopAudio();
      ws.current.send(JSON.stringify({ type: "hangup" }));
      setStatus("thinking");
    } else {
      reset();
    }
  }, [reset, stopAudio]);

  useEffect(() => reset, [reset]);

  return { phase, status, lines, error, start, startTalking, stopTalking, hangUp };
}
