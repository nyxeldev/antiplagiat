"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../lib/client-api";
import { IconLoader } from "./icons";
import Login from "./login/Login";
import AppShell from "./shell/AppShell";
const SessionContext = createContext<() => void>(() => {});
export const useSessionExpired = () => useContext(SessionContext);
type User = { id: string; username: string; role: string };
const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);
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
    catch (e) { if (e instanceof ApiError && e.status === 401) setUser(null); else setError(e instanceof Error ? e.message : "Chiqish bajarilmadi."); } finally { mutation.current = false; setBusy(false); }
  }
  if (loading) return (
    <div role="status" style={{ display: "grid", placeItems: "center", minHeight: "100svh", color: "var(--ink-on-dark-faint)", gap: "0.75rem" }}>
      <IconLoader style={{ width: "1.75rem", height: "1.75rem", animation: "spin 0.9s linear infinite" }} />
      <span style={{ fontSize: "var(--fs-sm)" }}>Session tekshirilmoqda…</span>
    </div>
  );
  if (!user) return <Login loginName={loginName} password={password} busy={busy} error={error}
    onLoginName={setLoginName} onPassword={setPassword} onSubmit={login} />;
  return <SessionContext.Provider value={expired}><UserContext.Provider value={user}>
    <AppShell user={user} onLogout={logout} busy={busy} error={error}><div key={user.id}>{children}</div></AppShell>
  </UserContext.Provider></SessionContext.Provider>;
}
