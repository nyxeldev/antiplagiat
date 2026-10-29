"use client";
import GeometricMotif from "./geometric-motif";
import { Rise } from "./motion";
import styles from "./page.module.css";

export default function Hero() {
  return (
    <Rise className={styles.intro}>
      <section aria-labelledby="page-title">
        <GeometricMotif className={styles.motif} aria-hidden="true" />
        <div className={styles.mark} aria-hidden="true">IA</div>
        <h1 id="page-title">Islom akademiyasi — Antiplagiat</h1>
        <p className={styles.description}>Ilmiy hujjatlardagi matn o‘xshashligini tekshirish platformasi.</p>
        <p className={styles.status}>Lokal ishlab chiqish rejimi. Hisobot matnlari hisobingizga bog‘lanib saqlanadi.</p>
      </section>
    </Rise>
  );
}
