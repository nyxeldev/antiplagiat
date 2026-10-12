import styles from "./page.module.css";

import Comparison from "./comparison";

export default function Home() {
  return (
    <main className={styles.page}>
      <section className={styles.intro} aria-labelledby="page-title">
        <div className={styles.mark} aria-hidden="true">IA</div>
        <h1 id="page-title">Islom akademiyasi — Antiplagiat</h1>
        <p className={styles.description}>
          Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.
        </p>
        <p className={styles.status}>Tizim ishlab chiqilmoqda. Faqat lokal foydalanish uchun prototip.</p>
      </section>
      <Comparison />
    </main>
  );
}
