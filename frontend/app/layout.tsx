import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Islom akademiyasi — Antiplagiat",
  description: "Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
