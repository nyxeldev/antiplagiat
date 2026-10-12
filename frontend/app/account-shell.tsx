"use client";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../lib/client-api";
import styles from "./page.module.css";
const SessionContext = createContext<() => void>(() => {});
export const useSessionExpired = () => useContext(SessionContext);
type User = { id: string; username: string; role: string };
export default function AccountShell({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null); const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const [loginName, setLoginName] = useState(""); const [password, setPassword] = useState("");
  const epoch = useRef(0); const mutation = useRef(false);
  const expired = useCallback(() => { epoch.current++; setUser(null); setError("Session tugagan. Qayta kiring."); }, []);
  useEffect(() => {
    let alive = true;
    async function check() {
      if (mutation.current) return;
      const current = ++epoch.current;
      try { const result = await api("/auth/me"); if (alive && current === epoch.current) { setUser(result.user); setError(null); } }
      catch (e) { if (alive && current === epoch.current) { if (e instanceof ApiError && e.status === 401) setUser(null); else setError(e instanceof Error ? e.message : "Session tekshirilmadi."); } }
      finally { if (alive && current === epoch.current) setLoading(false); }
    }
    void check(); window.addEventListener("focus", check); window.addEventListener("pageshow", check);
    return () => { alive = false; window.removeEventListener("focus", check); window.removeEventListener("pageshow", check); };
  }, []);
  async function login(event: FormEvent) {
    event.preventDefault(); if (mutation.current) return; mutation.current = true; epoch.current++; setBusy(true); setError(null);
    try { const result = await api("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: loginName, password }) }); setUser(result.user); }
    catch (e) { setError(e instanceof Error ? e.message : "Kirish bajarilmadi."); }
    finally { setPassword(""); mutation.current = false; setBusy(false); }
  }
  async function logout() {
    if (mutation.current) return; mutation.current = true; epoch.current++; setBusy(true); setError(null);
    try { await api("/auth/logout", { method: "POST" }); setUser(null); }
    catch (e) { if (e instanceof ApiError && e.status === 401) setUser(null); else setError(e instanceof Error ? e.message : "Chiqish bajarilmadi."); }
    finally { mutation.current = false; setBusy(false); }
  }
  if (loading) return <p role="status" className={styles.panel}>Session tekshirilmoqda…</p>;
  if (!user) return <form onSubmit={login} className={`${styles.panel} ${styles.login}`}><h2>Hisobga kirish</h2><p className={styles.muted}>Akkaunt lokal boshqaruv vositasi orqali yaratiladi.</p>
    <label htmlFor="username">Login</label><input id="username" autoComplete="username" required minLength={3} maxLength={64} value={loginName} disabled={busy} onChange={e => setLoginName(e.target.value)} />
    <label htmlFor="password">Parol</label><input id="password" type="password" autoComplete="current-password" required maxLength={256} value={password} disabled={busy} onChange={e => setPassword(e.target.value)} />
    <button className={styles.primary} disabled={busy}>{busy ? "Kirilmoqda…" : "Kirish"}</button>{error && <p role="alert" className={styles.error}>{error}</p>}</form>;
  return <SessionContext.Provider value={expired}><nav className={`${styles.panel} ${styles.account}`} aria-label="Hisob"><span>{user.username}</span><Link href="/">Yangi tekshiruv</Link><Link href="/history">Tekshiruvlar tarixi</Link><button onClick={logout} disabled={busy}>Chiqish</button></nav>{error && <p role="alert" className={styles.error}>{error}</p>}<div key={user.id}>{children}</div></SessionContext.Provider>;
}
