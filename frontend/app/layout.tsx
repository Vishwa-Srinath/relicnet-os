import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RelicNet OS — ZETA-26 Mission Control",
  description: "Interplanetary packet routing engine with live failure rerouting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-bg text-slate-200">{children}</body>
    </html>
  );
}
