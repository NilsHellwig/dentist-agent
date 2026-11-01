"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";
import { AppointmentActions, ErrorText, inputClass, labelClass, PageHeader, StatusBadge } from "@/components/admin/ui";
import { type Appointment, formatDay, formatTime, fullName, isoDate, query, useLoad } from "@/lib/admin";

export default function AppointmentsPage() {
  const [from, setFrom] = useState(isoDate(new Date()));
  const [to, setTo] = useState("");
  const [status, setStatus] = useState("scheduled");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search);
  const { data, error, reload } = useLoad<Appointment[]>(`/appointments${query({ from, to, status, q })}`);

  const days = new Map<string, Appointment[]>();
  for (const a of data ?? []) {
    const day = a.starts_at.slice(0, 10);
    days.set(day, [...(days.get(day) ?? []), a]);
  }

  return (
    <>
      <PageHeader title="Termine" onRefresh={reload} />

      <div className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <label className={labelClass}>
          Von
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={inputClass} />
        </label>
        <label className={labelClass}>
          Bis
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={inputClass} />
        </label>
        <label className={labelClass}>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputClass}>
            <option value="scheduled">Geplant</option>
            <option value="cancelled">Storniert</option>
            <option value="">Alle</option>
          </select>
        </label>
        <label className={labelClass}>
          Suche
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name oder Kundennummer"
            className={inputClass}
          />
        </label>
      </div>

      <ErrorText error={error} />
      {data?.length === 0 && <p className="text-sm text-muted">Keine Termine gefunden.</p>}

      <div className="space-y-10">
        {[...days].map(([day, appointments]) => (
          <section key={day}>
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-muted">{formatDay(day)}</h2>
            <ul className="divide-y divide-line border-y border-line">
              {appointments.map((a) => (
                <li key={a.id} className="flex flex-wrap items-start justify-between gap-4 py-4">
                  <div className="flex gap-6">
                    <span className="w-12 tabular-nums">{formatTime(a.starts_at)}</span>
                    <div>
                      <Link href={`/admin/kunden/${a.customer.id}`} className="hover:underline">
                        {fullName(a.customer)}
                      </Link>
                      <span className="ml-2 text-sm text-muted">{a.customer.customer_number}</span>
                      <p className="text-sm text-muted">{a.treatment}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-6">
                    <StatusBadge status={a.status} />
                    <AppointmentActions appointment={a} onChanged={reload} />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
