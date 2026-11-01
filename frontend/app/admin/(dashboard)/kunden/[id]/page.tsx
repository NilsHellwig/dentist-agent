"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AppointmentActions,
  buttonClass,
  ErrorText,
  inputClass,
  labelClass,
  linkButtonClass,
  PageHeader,
  SlotPicker,
  StatusBadge,
} from "@/components/admin/ui";
import { api, type CustomerDetail, formatDate, formatDateTime, formatEuro, fullName, TREATMENTS, useLoad } from "@/lib/admin";

export default function CustomerPage() {
  const { id } = useParams<{ id: string }>();
  const { data: customer, error, reload } = useLoad<CustomerDetail>(`/customers/${id}`);

  return (
    <>
      <Link href="/admin/kunden" className={linkButtonClass}>
        ← Alle Kunden
      </Link>
      <div className="mt-4">
        <PageHeader title={customer ? fullName(customer) : "Kunde"} onRefresh={reload}>
          {customer && <span className="text-sm text-muted">Kundennr. {customer.customer_number}</span>}
        </PageHeader>
      </div>
      <ErrorText error={error} />

      {customer && (
        <div className="space-y-14">
          <MasterData customer={customer} onSaved={reload} />
          <NewAppointment customerId={customer.id} onBooked={reload} />

          <section>
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-muted">Termine</h2>
            {customer.appointments.length === 0 && <p className="text-sm text-muted">Keine Termine.</p>}
            <ul className="divide-y divide-line border-y border-line empty:border-0">
              {customer.appointments.map((a) => (
                <li key={a.id} className="flex flex-wrap items-start justify-between gap-4 py-4">
                  <div>
                    <p className="tabular-nums">{formatDateTime(a.starts_at)}</p>
                    <p className="text-sm text-muted">{a.treatment}</p>
                  </div>
                  <div className="flex items-start gap-6">
                    <StatusBadge status={a.status} />
                    <AppointmentActions appointment={a} onChanged={reload} />
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-muted">Rechnungen</h2>
            {customer.invoices.length === 0 && <p className="text-sm text-muted">Keine Rechnungen.</p>}
            <ul className="divide-y divide-line border-y border-line empty:border-0">
              {customer.invoices.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                  <div>
                    <p>{i.description}</p>
                    <p className="text-sm tabular-nums text-muted">{formatDate(i.issued_on)}</p>
                  </div>
                  <div className="flex items-center gap-6">
                    <span className="tabular-nums">{formatEuro(i.amount_eur)}</span>
                    <StatusBadge status={i.status} />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}

function MasterData({ customer, onSaved }: { customer: CustomerDetail; onSaved: () => void }) {
  const initial = { first_name: customer.first_name, last_name: customer.last_name, birth_date: customer.birth_date };
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const dirty = JSON.stringify(form) !== JSON.stringify(initial);

  // pick up fresh data after a reload
  useEffect(() => setForm(initial), [customer]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/customers/${customer.id}`, { method: "PATCH", body: form });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-muted">Stammdaten</h2>
      <form onSubmit={save} className="flex flex-wrap items-end gap-4">
        <label className={labelClass}>
          Vorname
          <input value={form.first_name} onChange={(e) => (setForm({ ...form, first_name: e.target.value }), setSaved(false))} className={inputClass} required />
        </label>
        <label className={labelClass}>
          Nachname
          <input value={form.last_name} onChange={(e) => (setForm({ ...form, last_name: e.target.value }), setSaved(false))} className={inputClass} required />
        </label>
        <label className={labelClass}>
          Geburtsdatum
          <input
            type="date"
            value={form.birth_date}
            onChange={(e) => (setForm({ ...form, birth_date: e.target.value }), setSaved(false))}
            className={inputClass}
            required
          />
        </label>
        <button type="submit" disabled={!dirty} className={buttonClass}>
          Speichern
        </button>
        {saved && !dirty && <span className="text-sm text-accent">Gespeichert</span>}
      </form>
      <ErrorText error={error} />
    </section>
  );
}

function NewAppointment({ customerId, onBooked }: { customerId: number; onBooked: () => void }) {
  const [slot, setSlot] = useState("");
  const [treatment, setTreatment] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function book(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/appointments", { method: "POST", body: { customer_id: customerId, starts_at: slot, treatment } });
      setSlot("");
      setTreatment("");
      onBooked();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-muted">Termin anlegen</h2>
      <form onSubmit={book} className="flex flex-wrap items-end gap-4">
        <SlotPicker value={slot} onChange={setSlot} />
        <label className={labelClass}>
          Behandlung
          <input value={treatment} onChange={(e) => setTreatment(e.target.value)} list="treatments" className={inputClass} required />
          <datalist id="treatments">
            {TREATMENTS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </label>
        <button type="submit" disabled={!slot} className={buttonClass}>
          Buchen
        </button>
      </form>
      <ErrorText error={error} />
    </section>
  );
}
