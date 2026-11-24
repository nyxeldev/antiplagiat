"use client";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useSessionExpired, useUser } from "../account-shell";
import { IconKey } from "../icons";
import { Pop, Rise } from "../motion";
import { Alert, Button, Card, Field, PasswordInput } from "../ui/primitives";
import pageStyles from "../page.module.css";
import styles from "./profile.module.css";

const ROLE_LABEL: Record<string, string> = {
  talaba: "Talaba", ustoz: "Ustoz", kafedra_mudiri: "Kafedra mudiri", admin: "Admin", super_admin: "Super admin",
};

export default function ProfilePage() {
  const user = useUser();
  const expired = useSessionExpired();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const inFlight = useRef(false);

  if (!user) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!oldPassword || !newPassword || inFlight.current) return;
    if (newPassword !== confirmPassword) { setError("Yangi parollar bir xil emas."); return; }
    inFlight.current = true; setBusy(true); setError(null);
    try {
      await api("/auth/change-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      setDone(true);
      setTimeout(expired, 1800);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? "Joriy parol noto‘g‘ri."
        : e instanceof Error ? e.message : "Parol o‘zgartirilmadi.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <Rise>
    <Card className={styles.section}>
      <div className={pageStyles.sectionHeading}><h2>Profil</h2></div>
      <p className={pageStyles.muted}>Login: <strong>{user.username}</strong> · Rol: <strong>{ROLE_LABEL[user.role] ?? user.role}</strong></p>
    </Card>

    <Card className={styles.section}>
      <div className={pageStyles.sectionHeading}><h2>Parolni o‘zgartirish</h2></div>
      {done ? (
        <Alert variant="success">Parol o‘zgartirildi. Qayta kirishingiz kerak bo‘ladi…</Alert>
      ) : (
        <form onSubmit={submit} className={styles.formGrid}>
          <Field label="Joriy parol" htmlFor="profile-old-password">
            <PasswordInput id="profile-old-password" required autoComplete="current-password" value={oldPassword} disabled={busy}
              onChange={e => setOldPassword(e.target.value)} />
          </Field>
          <Field label="Yangi parol" htmlFor="profile-new-password" hint="Kamida 8 belgi.">
            <PasswordInput id="profile-new-password" required autoComplete="new-password" value={newPassword} disabled={busy}
              onChange={e => setNewPassword(e.target.value)} />
          </Field>
          <Field label="Yangi parolni takrorlang" htmlFor="profile-confirm-password">
            <PasswordInput id="profile-confirm-password" required autoComplete="new-password" value={confirmPassword} disabled={busy}
              onChange={e => setConfirmPassword(e.target.value)} />
          </Field>

          <Pop show={!!error}>{error && <Alert variant="error">{error}</Alert>}</Pop>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button type="submit" icon={<IconKey />} loading={busy}
              disabled={!oldPassword || !newPassword || !confirmPassword}>Parolni o‘zgartirish</Button>
          </div>
        </form>
      )}
    </Card>
  </Rise>;
}
