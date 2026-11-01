"use client";

import Link from "next/link";
import { useState } from "react";
import { ErrorText, inputClass, linkButtonClass, PageHeader, StatusBadge } from "@/components/admin/ui";
import { api, formatDate, formatEuro, fullName, type Invoice, query, useLoad } from "@/lib/admin";

export default function InvoicesPage() {
  const [status, setStatus] = useState("");
  const { data, error, reload } = useLoad<Invoice[]>(`/invoices${query({ status })}`);
  const [actionError, setActionError] = useState<string | null>(null);

  async function toggle(invoice: Invoice) {
    setActionError(null);
    try {
      await api(`/invoices/${invoice.id}`, { method: "PATCH", body: { status: invoice.status === "open" ? "paid" : "open" } });
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Rechnungen" onRefresh={reload}>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status" className={`${inputClass} w-auto`}>
          <option value="">Alle</option>
          <option value="open">Offen</option>
          <option value="paid">Bezahlt</option>
        </select>
      </PageHeader>

      <ErrorText error={error ?? actionError} />
      {data?.length === 0 && <p className="text-sm text-muted">Keine Rechnungen gefunden.</p>}

      {!!data?.length && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.15em] text-muted">
              <tr className="border-b border-line">
                <th className="py-3 font-normal">Datum</th>
                <th className="py-3 font-normal">Kunde</th>
                <th className="py-3 font-normal">Beschreibung</th>
                <th className="py-3 text-right font-normal">Betrag</th>
                <th className="py-3 pl-6 font-normal">Status</th>
                <th className="py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((i) => (
                <tr key={i.id}>
                  <td className="py-3 tabular-nums">{formatDate(i.issued_on)}</td>
                  <td className="py-3">
                    <Link href={`/admin/kunden/${i.customer.id}`} className="hover:underline">
                      {fullName(i.customer)}
                    </Link>
                  </td>
                  <td className="py-3">{i.description}</td>
                  <td className="py-3 text-right tabular-nums">{formatEuro(i.amount_eur)}</td>
                  <td className="py-3 pl-6">
                    <StatusBadge status={i.status} />
                  </td>
                  <td className="py-3 text-right">
                    <button onClick={() => toggle(i)} className={linkButtonClass}>
                      {i.status === "open" ? "Als bezahlt markieren" : "Als offen markieren"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
