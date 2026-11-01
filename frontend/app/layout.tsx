import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], weight: ["300", "400"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Praxis Nordlicht – Sprachassistenz",
  description: "Testoberfläche für den Voice-Agenten der Zahnarztpraxis",
};

export const viewport: Viewport = { themeColor: "#f5f2ec" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className={inter.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
