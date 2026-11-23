"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useSessionExpired, useUser } from "../account-shell";
import { ADMIN_ROLES } from "../shell/AppShell";
import { IconCheck, IconPlus, IconShield, IconUser, IconX } from "../icons";
import { Pop, Rise } from "../motion";
import { Alert, Badge, Button, Card, EmptyState, Field, IconButton, Input, PasswordInput, Select } from "../ui/primitives";
import { Dialog } from "../ui/Dialog";
import styles from "./admin.module.css";
import pageStyles from "../page.module.css";

const ROLE_LABEL: Record<string, string> = {
  talaba: "Talaba", ustoz: "Ustoz", kafedra_mudiri: "Kafedra mudiri", admin: "Admin", super_admin: "Super admin",
};
const ASSIGNABLE_ROLES = ["talaba", "ustoz", "kafedra_mudiri", "admin"];
const UNASSIGNED = "";

type AdminUser = {
  id: string; username: string; role: string; can_submit_to_corpus: boolean; enabled: boolean;
  kafedra_id: string | null; kafedra_nomi: string | null;
};
type Kafedra = { id: string; nomi: string; qisqa_kodi: string; created_at: string };

export default function AdminPanel() {
  const user = useUser();
  const expired = useSessionExpired();
  const allowed = !!user && ADMIN_ROLES.has(user.role);

  const [q, setQ] = useState("");
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [kafedraList, setKafedraList] = useState<Kafedra[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [addAccountOpen, setAddAccountOpen] = useState(false);
  const [addKafedraOpen, setAddKafedraOpen] = useState(false);

  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api(`/admin/users?q=${encodeURIComponent(q.trim())}`, { signal: controller.signal })
        .then(result => { setUsers(result.items); setError(null); })
        .catch(e => {
          if (controller.signal.aborted) return;
          if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Foydalanuvchilar ro‘yxati olinmadi.");
        });
    }, q ? 300 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [allowed, q, version, expired]);

  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    api("/admin/kafedra", { signal: controller.signal })
      .then(result => { setKafedraList(result.items); })
      .catch(e => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Kafedralar ro‘yxati olinmadi.");
      });
    return () => controller.abort();
  }, [allowed, version, expired]);

  function withBusy(id: string, task: () => Promise<void>) {
    setBusyIds(prev => new Set(prev).add(id));
    setError(null);
    task()
      .then(() => setVersion(v => v + 1))
      .catch(e => { if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Amalni bajarib bo‘lmadi."); })
      .finally(() => setBusyIds(prev => { const next = new Set(prev); next.delete(id); return next; }));
  }

  function changeRole(target: AdminUser, role: string) {
    withBusy(target.id, () => api(`/admin/users/${target.id}/role`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role }),
    }).then(() => undefined));
  }

  function changeKafedra(target: AdminUser, qisqaKodi: string) {
    withBusy(target.id, () => api(`/admin/users/${target.id}/kafedra`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ qisqa_kodi: qisqaKodi || null }),
    }).then(() => undefined));
  }

  function toggleSubmission(target: AdminUser) {
    withBusy(target.id, () => api(`/users/${target.id}/corpus-submission-access`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !target.can_submit_to_corpus }),
    }).then(() => undefined));
  }

  if (!user) return null;
  if (!allowed) {
    return <Rise><Card>
      <EmptyState icon={<IconShield />} title="Ruxsat yo‘q" description="Bu bo‘lim faqat administrator uchun." />
    </Card></Rise>;
  }

  return <Rise>
    <Card className={styles.section}>
      <div className={pageStyles.sectionHeading}>
        <h2>Foydalanuvchilar</h2>
        <Button icon={<IconPlus />} onClick={() => setAddAccountOpen(true)}>Yangi akkaunt</Button>
      </div>
      <p className={pageStyles.muted}>Rol tayinlash, kafedraga biriktirish va ustozlarga korpusga taklif qilish huquqini berish.</p>

      <Input placeholder="Login bo‘yicha qidirish" aria-label="Qidirish" value={q} onChange={e => setQ(e.target.value)}
        style={{ marginBottom: "var(--sp-4)" }} />

      {error && <Alert variant="error">{error} <button onClick={() => setVersion(v => v + 1)}
        style={{ background: "none", border: 0, color: "inherit", textDecoration: "underline", cursor: "pointer", font: "inherit" }}>Qayta urinish</button></Alert>}

      {users === null && !error ? <p className={pageStyles.muted}>Yuklanmoqda…</p> : users && (
        !users.length
          ? <EmptyState icon={<IconUser />} title="Topilmadi" description="Qidiruvga mos foydalanuvchi yo‘q." />
          : <div className={styles.table}>
              <div className={styles.headerRow}><span>Login</span><span>Rol</span><span>Kafedra</span><span /></div>
              {users.map(row => {
                const busy = busyIds.has(row.id);
                return <div key={row.id} className={styles.row}>
                  <div>
                    <div className={styles.username}>{row.username}</div>
                    {!row.enabled && <div className={styles.meta}>O‘chirilgan</div>}
                  </div>
                  {row.role === "super_admin" ? <Badge variant="accent">{ROLE_LABEL.super_admin}</Badge> : (
                    <Select className={styles.select} aria-label={`${row.username} roli`} value={row.role} disabled={busy}
                      onChange={e => changeRole(row, e.target.value)}>
                      {ASSIGNABLE_ROLES.map(role => <option key={role} value={role}>{ROLE_LABEL[role]}</option>)}
                    </Select>
                  )}
                  <Select className={styles.select} aria-label={`${row.username} kafedrasi`}
                    value={(row.kafedra_id && kafedraList?.find(k => k.id === row.kafedra_id)?.qisqa_kodi) || UNASSIGNED}
                    disabled={busy || !kafedraList} onChange={e => changeKafedra(row, e.target.value)}>
                    <option value={UNASSIGNED}>— biriktirilmagan —</option>
                    {kafedraList?.map(k => <option key={k.id} value={k.qisqa_kodi}>{k.nomi}</option>)}
                  </Select>
                  <span className={styles.actions}>
                    {row.role === "ustoz" && (
                      <>
                        <Badge variant={row.can_submit_to_corpus ? "accent" : "neutral"}>{row.can_submit_to_corpus ? "Taklif: bor" : "Taklif: yo‘q"}</Badge>
                        <IconButton label={row.can_submit_to_corpus ? "Taklif huquqini olib tashlash" : "Taklif huquqini berish"}
                          icon={row.can_submit_to_corpus ? <IconX /> : <IconCheck />} disabled={busy} onClick={() => toggleSubmission(row)} />
                      </>
                    )}
                  </span>
                </div>;
              })}
            </div>
      )}
    </Card>

    <Card className={styles.section}>
      <div className={pageStyles.sectionHeading}>
        <h2>Kafedralar</h2>
        <Button icon={<IconPlus />} onClick={() => setAddKafedraOpen(true)}>Yangi kafedra</Button>
      </div>
      {kafedraList === null && !error ? <p className={pageStyles.muted}>Yuklanmoqda…</p> : kafedraList && (
        !kafedraList.length
          ? <EmptyState icon={<IconShield />} title="Kafedra yo‘q" description="Hali birorta ham kafedra yaratilmagan." />
          : <div className={styles.kafedraTable}>
              {kafedraList.map(k => (
                <div key={k.id} className={styles.kafedraRow}>
                  <span className={styles.username}>{k.nomi}</span>
                  <Badge>{k.qisqa_kodi}</Badge>
                  <span className={styles.meta}>{new Date(k.created_at).toLocaleDateString("uz-UZ")}</span>
                </div>
              ))}
            </div>
      )}
    </Card>

    <AddAccountDialog open={addAccountOpen} onClose={() => setAddAccountOpen(false)}
      onAdded={() => { setAddAccountOpen(false); setVersion(v => v + 1); }} />
    <AddKafedraDialog open={addKafedraOpen} onClose={() => setAddKafedraOpen(false)}
      onAdded={() => { setAddKafedraOpen(false); setVersion(v => v + 1); }} />
  </Rise>;
}

function AddAccountDialog({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const expired = useSessionExpired();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("talaba");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  function reset() { setUsername(""); setPassword(""); setRole("talaba"); setError(null); }
  function close() { if (busy) return; reset(); onClose(); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      await api("/admin/users", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password, role }),
      });
      reset(); onAdded();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Akkaunt yaratilmadi.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <Dialog open={open} onClose={close} title="Yangi akkaunt yaratish">
    <form onSubmit={submit} className={styles.formGrid}>
      <Field label="Login" htmlFor="admin-new-username">
        <Input id="admin-new-username" required maxLength={100} value={username} disabled={busy}
          onChange={e => setUsername(e.target.value)} />
      </Field>
      <Field label="Parol" htmlFor="admin-new-password" hint="Kamida 12 belgi.">
        <PasswordInput id="admin-new-password" required value={password} disabled={busy}
          onChange={e => setPassword(e.target.value)} />
      </Field>
      <Field label="Rol" htmlFor="admin-new-role">
        <Select id="admin-new-role" value={role} disabled={busy} onChange={e => setRole(e.target.value)}>
          {ASSIGNABLE_ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
        </Select>
      </Field>

      <Pop show={!!error}>{error && <Alert variant="error">{error}</Alert>}</Pop>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--sp-3)" }}>
        <Button type="button" variant="secondary" onClick={close} disabled={busy}>Bekor qilish</Button>
        <Button type="submit" loading={busy} disabled={!username.trim() || !password}>Yaratish</Button>
      </div>
    </form>
  </Dialog>;
}

function AddKafedraDialog({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const expired = useSessionExpired();
  const [nomi, setNomi] = useState("");
  const [qisqaKodi, setQisqaKodi] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  function reset() { setNomi(""); setQisqaKodi(""); setError(null); }
  function close() { if (busy) return; reset(); onClose(); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!nomi.trim() || !qisqaKodi.trim() || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      await api("/admin/kafedra", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nomi: nomi.trim(), qisqa_kodi: qisqaKodi.trim() }),
      });
      reset(); onAdded();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Kafedra yaratilmadi.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <Dialog open={open} onClose={close} title="Yangi kafedra yaratish">
    <form onSubmit={submit} className={styles.formGrid}>
      <Field label="Nomi" htmlFor="admin-new-kafedra-nomi">
        <Input id="admin-new-kafedra-nomi" required maxLength={300} value={nomi} disabled={busy}
          onChange={e => setNomi(e.target.value)} />
      </Field>
      <Field label="Qisqa kod" htmlFor="admin-new-kafedra-kodi" hint="Masalan: dasturiy-injiniring">
        <Input id="admin-new-kafedra-kodi" required maxLength={32} value={qisqaKodi} disabled={busy}
          onChange={e => setQisqaKodi(e.target.value)} />
      </Field>

      <Pop show={!!error}>{error && <Alert variant="error">{error}</Alert>}</Pop>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--sp-3)" }}>
        <Button type="button" variant="secondary" onClick={close} disabled={busy}>Bekor qilish</Button>
        <Button type="submit" loading={busy} disabled={!nomi.trim() || !qisqaKodi.trim()}>Yaratish</Button>
      </div>
    </form>
  </Dialog>;
}
