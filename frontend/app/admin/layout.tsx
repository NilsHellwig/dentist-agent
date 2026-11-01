import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verwaltung – Praxis Nordlicht",
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
