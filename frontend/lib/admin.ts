"use client";

import { useCallback, useEffect, useState } from "react";

export type AppointmentStatus = "scheduled" | "cancelled";
export type InvoiceStatus = "open" | "paid";

export type CustomerRef = { id: number; customer_number: string; first_name: string; last_name: string };
export type Customer = CustomerRef & { birth_date: string };
export type Appointment = { id: number; starts_at: string; treatment: string; status: AppointmentStatus; customer: CustomerRef };
export type Invoice = {
  id: number;
  issued_on: string;
  description: string;
  amount_eur: number;
  status: InvoiceStatus;
  customer: CustomerRef;
};
export type CustomerDetail = Customer & { appointments: Appointment[]; invoices: Invoice[] };

export const STATUS_LABELS: Record<AppointmentStatus | InvoiceStatus, string> = {
  scheduled: "Geplant",
  cancelled: "Storniert",
  open: "Offen",
  paid: "Bezahlt",
};

export const TREATMENTS = [
  "Kontrolluntersuchung",
  "Professionelle Zahnreinigung",
  "Prophylaxe",
  "Kinder-Kontrolle",
  "Füllung",
  "Beratung",
];

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const resp = await fetch(`/admin/api${path}`, {
    method: init.method ?? "GET",
    headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    cache: "no-store",
  });
  if (resp.status === 401) {
    window.location.assign("/admin/login");
    throw new Error("Nicht angemeldet.");
  }
  if (!resp.ok) {
    const detail = await resp.json().then((d) => d.detail, () => null);
    // FastAPI validation errors come as a list of field errors
    throw new Error(typeof detail === "string" ? detail : resp.status === 422 ? "Eingabe ungültig." : `Fehler ${resp.status}`);
  }
  return resp.status === 204 ? (undefined as T) : resp.json();
}

/** Loads data on mount and whenever `path` changes; `reload` refetches on demand. */
export function useLoad<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api<T>(path).then(
      (d) => !cancelled && (setData(d), setError(null)),
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, reload };
}

export function query(params: Record<string, string>): string {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
  return q.size ? `?${q}` : "";
}

/** YYYY-MM-DD in local time (toISOString would shift to UTC). */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Date-only strings would be parsed as UTC midnight; treat them as local
const toDate = (s: string) => new Date(s.length === 10 ? `${s}T00:00` : s);

export const formatDay = (s: string) =>
  toDate(s).toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
export const formatDate = (s: string) => toDate(s).toLocaleDateString("de-DE");
export const formatTime = (s: string) => new Date(s).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
export const formatDateTime = (s: string) => `${formatDate(s)}, ${formatTime(s)} Uhr`;
export const formatEuro = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR" });
export const fullName = (c: CustomerRef) => `${c.first_name} ${c.last_name}`;
