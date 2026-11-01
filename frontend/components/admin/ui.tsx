"use client";

import { useState } from "react";
import { api, type Appointment, formatTime, isoDate, STATUS_LABELS, useLoad } from "@/lib/admin";

export const buttonClass =
  "rounded-full border border-ink/80 px-4 py-1.5 text-sm transition-colors hover:bg-ink hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-40";
export const linkButtonClass =
  "text-sm text-muted underline-offset-4 transition-colors hover:text-ink hover:underline focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-40";
export const inputClass =
  "w-full rounded-md border border-line bg-white/60 px-3 py-2 text-sm normal-case tracking-normal text-ink placeholder:text-muted focus:border-accent focus:outline-none";
export const labelClass = "flex flex-col gap-1 text-xs uppercase tracking-[0.15em] text-muted";

export function PageHeader({ title, onRefresh, children }: { title: string; onRefresh?: () => void; children?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <h1 className="text-3xl font-light tracking-tight">{title}</h1>
      <div className="flex items-center gap-4">
        {children}
        {onRefresh && (
          <button onClick={onRefresh} className={linkButtonClass}>
            Aktualisieren
          </button>
        )}
      </div>
    </div>
  );
}

export function ErrorText({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p className="text-sm text-[#a05a4a]" role="alert">
      {error}
    </p>
  );
}

export function StatusBadge({ status }: { status: keyof typeof STATUS_LABELS }) {
  const muted = status === "cancelled" || status === "paid";
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs ${muted ? "bg-line/60 text-muted" : "bg-accent/15 text-accent"}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

/** Date input plus a select of the free slots on that day; `onChange` receives the slot's ISO datetime. */
export function SlotPicker({ value, onChange }: { value: string; onChange: (slot: string) => void }) {
  const [day, setDay] = useState(isoDate(new Date()));
  const { data: slots, error } = useLoad<string[]>(day ? `/free-slots?day=${day}` : null);

  return (
    <div className="flex flex-wrap gap-3">
      <label className={labelClass}>
        Datum
        <input
          type="date"
          value={day}
          min={isoDate(new Date())}
          onChange={(e) => {
            setDay(e.target.value);
            onChange("");
          }}
          className={inputClass}
          required
        />
      </label>
      <label className={labelClass}>
        Uhrzeit
        <select value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} required>
          <option value="">{slots?.length === 0 ? "Keine freien Zeiten" : "Bitte wählen"}</option>
          {slots?.map((s) => (
            <option key={s} value={s}>
              {formatTime(s)}
            </option>
          ))}
        </select>
      </label>
      <ErrorText error={error} />
    </div>
  );
}

/** Reschedule and cancel controls for one appointment. */
export function AppointmentActions({ appointment, onChanged }: { appointment: Appointment; onChanged: () => void }) {
  const [moving, setMoving] = useState(false);
  const [slot, setSlot] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (appointment.status !== "scheduled") return null;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setMoving(false);
      setSlot("");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const cancel = () => {
    if (!confirm("Termin wirklich stornieren?")) return;
    run(() => api(`/appointments/${appointment.id}/cancel`, { method: "POST" }));
  };
  const reschedule = (e: React.FormEvent) => {
    e.preventDefault();
    run(() => api(`/appointments/${appointment.id}`, { method: "PATCH", body: { starts_at: slot } }));
  };

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex gap-4">
        <button onClick={() => setMoving((m) => !m)} disabled={busy} className={linkButtonClass}>
          {moving ? "Abbrechen" : "Verschieben"}
        </button>
        <button onClick={cancel} disabled={busy} className={linkButtonClass}>
          Stornieren
        </button>
      </div>
      {moving && (
        <form onSubmit={reschedule} className="flex flex-wrap items-end justify-end gap-3">
          <SlotPicker value={slot} onChange={setSlot} />
          <button type="submit" disabled={busy || !slot} className={buttonClass}>
            Speichern
          </button>
        </form>
      )}
      <ErrorText error={error} />
    </div>
  );
}
