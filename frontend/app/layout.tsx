import type { Metadata } from "next";
import "./globals.css";
import AccountShell from "./account-shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Islom akademiyasi — Antiplagiat",
  description: "Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body><main className={styles.page}><section className={styles.intro} aria-labelledby="page-title"><div className={styles.mark} aria-hidden="true">IA</div><h1 id="page-title">Islom akademiyasi — Antiplagiat</h1><p className={styles.description}>Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.</p><p className={styles.status}>Lokal ishlab chiqish rejimi. Hisobot matnlari hisobingizga bog‘lanib saqlanadi.</p></section><AccountShell>{children}</AccountShell></main></body>
    </html>
  );
}
