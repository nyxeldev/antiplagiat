"use client";
import type { FormEvent } from "react";
import { Rise } from "../motion";
import { Alert, Button, Field, Input, PasswordInput } from "../ui/primitives";
import CompareIllustration from "./compare-illustration";
import styles from "./login.module.css";

export default function Login({
  loginName, password, busy, error, onLoginName, onPassword, onSubmit,
}: {
  loginName: string; password: string; busy: boolean; error: string | null;
  onLoginName: (v: string) => void; onPassword: (v: string) => void; onSubmit: (e: FormEvent) => void;
}) {
  return (
    <div className={styles.screen}>
      <section className={styles.visual} aria-hidden="true">
        <div className={styles.visualBrand}>
          <span className={styles.visualMark}>IA</span>
          <strong style={{ fontFamily: "var(--font-display)" }}>Islom akademiyasi — Antiplagiat</strong>
        </div>
        <CompareIllustration className={styles.visualIllustration} />
        <h1>Ilmiy hujjatlardagi matn o‘xshashligini aniq va tushunarli tekshiring</h1>
        <p>Tekshiriladigan hujjatni manba matnlari bilan solishtirib, mos parchalarni aniq joyi va foizi bilan ko‘rsatadigan platforma.</p>
        <p className={styles.visualNote}>Yuqoridagi tasvir — illyustrativ, haqiqiy tekshiruv natijasi emas.</p>
      </section>
      <section className={styles.formSide}>
        <Rise className={styles.formCard}>
          <div className={styles.mobileBrand}>
            <span className={styles.visualMark} aria-hidden="true">IA</span>
            <strong style={{ fontFamily: "var(--font-display)" }}>Islom akademiyasi — Antiplagiat</strong>
          </div>
          <form onSubmit={onSubmit} noValidate>
            <h2>Hisobga kirish</h2>
            <p>Akkaunt lokal boshqaruv vositasi orqali yaratiladi.</p>
            <div className={styles.formGrid}>
              <Field label="Login" htmlFor="username">
                <Input id="username" name="username" autoComplete="username" required minLength={3} maxLength={64}
                  value={loginName} disabled={busy} onChange={e => onLoginName(e.target.value)} />
              </Field>
              <Field label="Parol" htmlFor="password">
                <PasswordInput id="password" name="password" autoComplete="current-password" required maxLength={256}
                  value={password} disabled={busy} onChange={e => onPassword(e.target.value)} />
              </Field>
              <Button type="submit" loading={busy} className={styles.submit}>{busy ? "Kirilmoqda…" : "Kirish"}</Button>
              {error && <Alert variant="error">{error}</Alert>}
            </div>
          </form>
        </Rise>
      </section>
    </div>
  );
}
