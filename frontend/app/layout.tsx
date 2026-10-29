import type { Metadata } from "next";
import "./globals.css";
import AccountShell from "./account-shell";
import Hero from "./hero";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Islom akademiyasi — Antiplagiat",
  description: "Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body><main className={styles.page}><Hero /><AccountShell>{children}</AccountShell></main></body>
    </html>
  );
}
