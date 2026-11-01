"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/admin";

const NAV = [
  { href: "/admin", label: "Termine" },
  { href: "/admin/kunden", label: "Kunden" },
  { href: "/admin/rechnungen", label: "Rechnungen" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await api("/logout", { method: "POST" }).catch(() => undefined);
    router.push("/admin/login");
  }

  return (
    <div className="mx-auto min-h-dvh max-w-5xl px-6 py-8">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-5">
        <span className="text-xs uppercase tracking-[0.3em] text-muted">Nordlicht · Verwaltung</span>
        <nav className="flex gap-6 text-sm">
          {NAV.map(({ href, label }) => {
            const active = href === "/admin" ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`transition-colors hover:text-ink ${active ? "text-ink underline underline-offset-8" : "text-muted"}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <button onClick={logout} className="text-xs uppercase tracking-[0.2em] text-muted transition-colors hover:text-ink">
          Abmelden
        </button>
      </header>
      <main className="animate-fade-in">{children}</main>
    </div>
  );
}
