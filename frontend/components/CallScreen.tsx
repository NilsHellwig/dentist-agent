"use client";

import { useEffect, useRef } from "react";
import type { Line, Status, useCall } from "@/lib/useCall";

const LABELS: Record<Status, string> = {
  thinking: "Einen Moment …",
  speaking: "Spricht",
  ready: "Halten zum Sprechen",
  listening: "Ich höre zu",
};

export function CallScreen({ call }: { call: ReturnType<typeof useCall> }) {
  const { phase, status, lines, startTalking, stopTalking, hangUp } = call;
  const closing = phase === "closing";
  const endRef = useRef<HTMLDivElement>(null);

  // Space bar as push-to-talk
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      e.preventDefault();
      startTalking();
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") stopTalking();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [startTalking, stopTalking]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  const listening = status === "listening";

  return (
    <div className="animate-fade-in flex flex-1 flex-col">
      <header className="flex items-center justify-between text-xs uppercase tracking-[0.3em] text-muted">
        <span>Nordlicht</span>
        <button
          onClick={hangUp}
          disabled={closing}
          className="tracking-[0.2em] transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-0"
        >
          Auflegen
        </button>
      </header>

      <section className="flex flex-col items-center pt-16" aria-live="polite">
        <div className="relative flex h-32 w-32 items-center justify-center">
          {listening && <span className="animate-pulse-ring absolute inset-0 rounded-full border border-accent" />}
          <span
            className={`h-24 w-24 rounded-full bg-accent/80 transition-transform duration-500 ${
              status === "speaking" ? "animate-breathe" : listening ? "scale-110" : status === "thinking" ? "scale-90 opacity-50" : ""
            }`}
          />
        </div>
        <p className="mt-8 text-sm tracking-wide text-muted">{closing ? "Auf Wiederhören" : LABELS[status]}</p>
      </section>

      <section className="mt-10 flex-1 space-y-4 overflow-y-auto pb-6" aria-label="Gesprächsverlauf">
        {lines.map((l, i) =>
          l.role === "tool" ? (
            <ToolLine key={i} line={l} />
          ) : (
            <p
              key={i}
              className={`animate-fade-in text-[15px] leading-relaxed ${l.role === "user" ? "text-right text-muted" : "text-ink"}`}
            >
              {l.text}
            </p>
          ),
        )}
        <div ref={endRef} />
      </section>

      <footer className="flex flex-col items-center gap-3 pb-2 pt-4">
        <button
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            startTalking();
          }}
          onPointerUp={stopTalking}
          onPointerCancel={stopTalking}
          onContextMenu={(e) => e.preventDefault()}
          disabled={closing || status === "thinking"}
          className={`select-none touch-none rounded-full border px-12 py-5 text-sm tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:opacity-30 ${
            listening ? "border-accent bg-accent text-paper" : "border-ink/80 hover:bg-ink hover:text-paper"
          }`}
        >
          {listening ? "Loslassen zum Senden" : "Sprechen"}
        </button>
        <p className="text-xs text-muted">Taste halten oder Leertaste gedrückt halten</p>
      </footer>
    </div>
  );
}

function ToolLine({ line }: { line: Extract<Line, { role: "tool" }> }) {
  const args = Object.entries(line.args)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return (
    <details className="animate-fade-in group font-mono text-xs text-muted">
      <summary className="cursor-pointer list-none truncate hover:text-ink">
        <span className={line.result === undefined ? "animate-pulse" : ""}>{line.result === undefined ? "◌" : "●"}</span>{" "}
        {line.name}
        {args && <span className="opacity-70">({args})</span>}
      </summary>
      <pre className="mt-1 whitespace-pre-wrap break-words border-l border-line pl-3 opacity-80">{line.result ?? "läuft …"}</pre>
    </details>
  );
}
