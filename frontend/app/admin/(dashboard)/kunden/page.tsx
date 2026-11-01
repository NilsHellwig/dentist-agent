"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { buttonClass, ErrorText, inputClass, labelClass, linkButtonClass, PageHeader } from "@/components/admin/ui";
import { api, type Customer, formatDate, query, useLoad } from "@/lib/admin";

export default function CustomersPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search);
  const { data, error, reload } = useLoad<Customer[]>(`/customers${query({ q })}`);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", birth_date: "" });
  const [createError, setCreateError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    try {
      const customer = await api<Customer>("/customers", { method: "POST", body: form });
      router.push(`/admin/kunden/${customer.id}`);
    } catch (err) {
      setCreateError((err as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Kunden" onRefresh={reload}>
        <button onClick={() => setCreating((c) => !c)} className={linkButtonClass}>
          {creating ? "Abbrechen" : "Neuer Kunde"}
        </button>
      </PageHeader>

      {creating && (
        <form onSubmit={create} className="mb-10 flex flex-wrap items-end gap-4 rounded-lg border border-line p-5">
          <label className={labelClass}>
            Vorname
            <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className={inputClass} required />
          </label>
          <label className={labelClass}>
            Nachname
            <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className={inputClass} required />
          </label>
          <label className={labelClass}>
            Geburtsdatum
            <input
              type="date"
              value={form.birth_date}
              onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
              className={inputClass}
              required
            />
          </label>
          <button type="submit" className={buttonClass}>
            Anlegen
          </button>
          <p className="w-full text-xs text-muted">Die Kundennummer wird automatisch vergeben.</p>
          <ErrorText error={createError} />
        </form>
      )}

      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Name oder Kundennummer"
        aria-label="Kunden suchen"
        className={`${inputClass} mb-6 max-w-sm`}
      />
      <ErrorText error={error} />
      {data?.length === 0 && <p className="text-sm text-muted">Keine Kunden gefunden.</p>}

      {!!data?.length && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.15em] text-muted">
              <tr className="border-b border-line">
                <th className="py-3 font-normal">Kundennr.</th>
                <th className="py-3 font-normal">Name</th>
                <th className="py-3 font-normal">Geburtsdatum</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((c) => (
                <tr key={c.id} className="hover:bg-line/30">
                  <td className="py-3 tabular-nums text-muted">{c.customer_number}</td>
                  <td className="py-3">
                    <Link href={`/admin/kunden/${c.id}`} className="hover:underline">
                      {c.last_name}, {c.first_name}
                    </Link>
                  </td>
                  <td className="py-3 tabular-nums">{formatDate(c.birth_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
