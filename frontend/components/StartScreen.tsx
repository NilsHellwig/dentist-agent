type Props = { connecting: boolean; error: string | null; onStart: () => void };

export function StartScreen({ connecting, error, onStart }: Props) {
  return (
    <div className="animate-fade-in flex flex-1 flex-col items-center text-center">
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-xs uppercase tracking-[0.3em] text-muted">Zahnarztpraxis</p>
        <h1 className="mt-4 text-5xl font-light tracking-tight">Nordlicht</h1>
        <p className="mt-6 max-w-xs text-base leading-relaxed text-muted">
          Fragen zu Terminen, Leistungen oder Rechnungen? Sprechen Sie einfach mit unserer Assistenz.
        </p>

        <button
          onClick={onStart}
          disabled={connecting}
          className="mt-14 rounded-full border border-ink/80 px-10 py-4 text-sm tracking-wide transition-colors hover:bg-ink hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:opacity-40"
        >
          {connecting ? "Verbinde …" : "Gespräch starten"}
        </button>

        <p className="mt-6 h-5 text-sm text-[#a05a4a]" role="alert">
          {error}
        </p>
      </div>
      <p className="text-xs text-muted">Ein Mikrofon wird benötigt.</p>
    </div>
  );
}
