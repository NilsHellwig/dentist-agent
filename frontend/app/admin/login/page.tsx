"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { buttonClass, ErrorText, inputClass, labelClass } from "@/components/admin/ui";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    // plain fetch: the shared api() helper would redirect here again on 401
    const resp = await fetch("/admin/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }).catch(() => null);
    setBusy(false);
    if (resp?.ok) return router.push("/admin");
    const detail = await resp?.json().then((d) => d.detail, () => null);
    setError(typeof detail === "string" ? detail : "Server nicht erreichbar.");
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <p className="text-xs uppercase tracking-[0.3em] text-muted">Nordlicht</p>
      <h1 className="mt-3 text-4xl font-light tracking-tight">Verwaltung</h1>
      <form onSubmit={submit} className="mt-10 flex flex-col gap-5">
        <label className={labelClass}>
          Benutzername
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className={inputClass} required />
        </label>
        <label className={labelClass}>
          Passwort
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className={inputClass}
            required
          />
        </label>
        <ErrorText error={error} />
        <button type="submit" disabled={busy} className={`${buttonClass} mt-2 self-start px-8 py-2.5`}>
          {busy ? "Anmelden …" : "Anmelden"}
        </button>
      </form>
    </main>
  );
}
