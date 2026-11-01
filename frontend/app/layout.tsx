import type { Metadata } from "next";
import "./globals.css";
import AccountShell from "./account-shell";

export const metadata: Metadata = {
  title: "Islom akademiyasi — Antiplagiat",
  description: "Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body><AccountShell>{children}</AccountShell></body>
    </html>
  );
}
