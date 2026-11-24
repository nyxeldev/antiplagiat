"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useRefreshUser, useSessionExpired, useUser } from "../account-shell";
import { useAvatarUrl } from "../use-avatar-url";
import { IconKey, IconLogout, IconMonitor, IconTrash, IconUpload, IconUser } from "../icons";
import { Pop, Rise } from "../motion";
import { Alert, Avatar, Badge, Button, Card, EmptyState, Field, Input, PasswordInput, Skeleton } from "../ui/primitives";
import { ConfirmDialog } from "../ui/Dialog";
import { Dropzone } from "../ui/Dropzone";
import pageStyles from "../page.module.css";
import styles from "./profile.module.css";

const ROLE_LABEL: Record<string, string> = {
  talaba: "Talaba", ustoz: "Ustoz", kafedra_mudiri: "Kafedra mudiri", admin: "Admin", super_admin: "Super admin",
};
const AVATAR_TYPES = /^image\/(png|jpeg|webp)$/;
const MAX_AVATAR_BYTES = 1024 * 1024;

type Session = { created_at: string; expires_at: string; is_current: boolean };

export default function ProfilePage() {
  const user = useUser();
  if (!user) return null;
  return <Rise>
    <ProfileCard />
    <AccountCard />
    <SessionsCard />
  </Rise>;
}

function ProfileCard() {
  const user = useUser();
  const expired = useSessionExpired();
  const refreshUser = useRefreshUser();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  // Re-sync the draft whenever the server value changes under us (e.g. after
  // refreshUser()) -- adjusted during render, not in an effect, so it never
  // causes an extra commit (see https://react.dev/learn/you-might-not-need-an-effect).
  const [syncedWith, setSyncedWith] = useState(user?.full_name ?? null);
  const [nameBusy, setNameBusy] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);
  const nameInFlight = useRef(false);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removeBusy, setRemoveBusy] = useState(false);
  const avatarInFlight = useRef(false);

  const avatarUrl = useAvatarUrl(user);
  if (!user) return null;
  if (user.full_name !== syncedWith) { setSyncedWith(user.full_name ?? null); setFullName(user.full_name ?? ""); }
  const unchangedName = fullName.trim() === (user.full_name ?? "");

  async function submitName(event: FormEvent) {
    event.preventDefault();
    if (nameInFlight.current || unchangedName) return;
    nameInFlight.current = true; setNameBusy(true); setNameError(null); setNameSaved(false);
    try {
      await api("/auth/full-name", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name: fullName }) });
      refreshUser(); setNameSaved(true); setTimeout(() => setNameSaved(false), 3000);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setNameError(e instanceof Error ? e.message : "To‘liq ism saqlanmadi.");
    } finally { nameInFlight.current = false; setNameBusy(false); }
  }

  function pick(files: File[]) {
    const picked = files[0]; if (!picked) return;
    if (!AVATAR_TYPES.test(picked.type)) { setAvatarError("Faqat PNG, JPEG yoki WEBP rasm tanlang."); return; }
    if (picked.size > MAX_AVATAR_BYTES) { setAvatarError("Rasm 1 MiB dan oshmasligi kerak."); return; }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setAvatarError(null); setFile(picked); setPreviewUrl(URL.createObjectURL(picked));
  }

  function cancelPick() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null); setPreviewUrl(null); setAvatarError(null);
  }

  async function upload() {
    if (!file || avatarInFlight.current) return;
    avatarInFlight.current = true; setAvatarBusy(true); setAvatarError(null);
    const body = new FormData(); body.append("file", file);
    try {
      await api("/auth/avatar", { method: "POST", body });
      cancelPick(); refreshUser();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setAvatarError(e instanceof Error ? e.message : "Rasm yuklanmadi.");
    } finally { avatarInFlight.current = false; setAvatarBusy(false); }
  }

  async function removeAvatar() {
    setRemoveBusy(true); setAvatarError(null);
    try {
      await api("/auth/avatar", { method: "DELETE" });
      setRemoving(false); refreshUser();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setAvatarError(e instanceof Error ? e.message : "Rasm o‘chirilmadi.");
    } finally { setRemoveBusy(false); }
  }

  return <Card className={styles.section}>
    <div className={pageStyles.sectionHeading}><h2>Profil</h2></div>
    <div className={styles.identity}>
      <Avatar size="4.5rem" src={previewUrl ?? avatarUrl} fallback={<IconUser />} />
      <div>
        <p className={pageStyles.muted}>Login: <strong>{user.username}</strong> · Rol: <strong>{ROLE_LABEL[user.role] ?? user.role}</strong></p>
        {user.kafedra_nomi && <p className={pageStyles.muted}>Kafedra: <strong>{user.kafedra_nomi}</strong></p>}
        {user.created_at && <p className={pageStyles.muted}>Ro‘yxatdan o‘tgan: {new Date(user.created_at).toLocaleDateString("uz-UZ")}</p>}
      </div>
    </div>

    <form onSubmit={submitName} className={styles.inlineForm}>
      <Field label="To‘liq ism" htmlFor="profile-full-name" hint="Bo‘sh qoldirilsa, login ko‘rsatiladi.">
        <Input id="profile-full-name" maxLength={120} value={fullName} disabled={nameBusy}
          placeholder={user.username} onChange={e => setFullName(e.target.value)} />
      </Field>
      <Pop show={!!nameError}>{nameError && <Alert variant="error">{nameError}</Alert>}</Pop>
      <Pop show={nameSaved}>{nameSaved && <Alert variant="success">Saqlandi.</Alert>}</Pop>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button type="submit" loading={nameBusy} disabled={unchangedName}>Saqlash</Button>
      </div>
    </form>

    <div className={styles.divider}>
      <h3 className={styles.subHeading}>Profil rasmi</h3>
      <div className={styles.avatarActions}>
        {!file ? (
          <>
            <Dropzone label="Rasm tanlang yoki shu yerga tashlang" hint="PNG, JPEG yoki WEBP, 1 MiB gacha."
              accept="image/png,image/jpeg,image/webp" onFiles={pick} />
            {user.has_avatar && <Button variant="secondary" icon={<IconTrash />} onClick={() => setRemoving(true)}>Rasmni olib tashlash</Button>}
          </>
        ) : (
          <>
            <p className={pageStyles.muted}>{file.name}</p>
            <div style={{ display: "flex", gap: "var(--sp-3)" }}>
              <Button variant="secondary" onClick={cancelPick} disabled={avatarBusy}>Bekor qilish</Button>
              <Button icon={<IconUpload />} loading={avatarBusy} onClick={upload}>Yuklash</Button>
            </div>
          </>
        )}
        <Pop show={!!avatarError}>{avatarError && <Alert variant="error">{avatarError}</Alert>}</Pop>
      </div>
    </div>
    <ConfirmDialog open={removing} onClose={() => setRemoving(false)} onConfirm={removeAvatar}
      title="Rasmni olib tashlash" confirmLabel="Olib tashlash" busy={removeBusy}
      description="Profil rasmi o‘chiriladi." />
  </Card>;
}

function AccountCard() {
  const user = useUser();
  const expired = useSessionExpired();
  const refreshUser = useRefreshUser();
  const [username, setUsername] = useState(user?.username ?? "");
  const [syncedWith, setSyncedWith] = useState(user?.username ?? "");
  const [userBusy, setUserBusy] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);
  const [userSaved, setUserSaved] = useState(false);
  const userInFlight = useRef(false);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordDone, setPasswordDone] = useState(false);
  const passwordInFlight = useRef(false);

  if (!user) return null;
  if (user.username !== syncedWith) { setSyncedWith(user.username); setUsername(user.username); }
  const unchangedUsername = username === user.username;

  async function submitUsername(event: FormEvent) {
    event.preventDefault();
    if (userInFlight.current || unchangedUsername) return;
    userInFlight.current = true; setUserBusy(true); setUserError(null); setUserSaved(false);
    try {
      await api("/auth/username", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) });
      refreshUser(); setUserSaved(true); setTimeout(() => setUserSaved(false), 3000);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setUserError(e instanceof Error ? e.message : "Login o‘zgartirilmadi.");
    } finally { userInFlight.current = false; setUserBusy(false); }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (!oldPassword || !newPassword || passwordInFlight.current) return;
    if (newPassword !== confirmPassword) { setPasswordError("Yangi parollar bir xil emas."); return; }
    passwordInFlight.current = true; setPasswordBusy(true); setPasswordError(null);
    try {
      await api("/auth/change-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      setPasswordDone(true);
      setTimeout(expired, 1800);
    } catch (e) {
      setPasswordError(e instanceof ApiError && e.status === 401 ? "Joriy parol noto‘g‘ri."
        : e instanceof Error ? e.message : "Parol o‘zgartirilmadi.");
    } finally { passwordInFlight.current = false; setPasswordBusy(false); }
  }

  return <Card className={styles.section}>
    <div className={pageStyles.sectionHeading}><h2>Hisob</h2></div>
    <div className={styles.twoCol}>
      <form onSubmit={submitUsername} className={styles.formGrid}>
        <h3 className={styles.subHeading}>Login</h3>
        <Field label="Yangi login" htmlFor="profile-username" hint="3-64 kichik lotin harfi, son, _ . -">
          <Input id="profile-username" required minLength={3} maxLength={64} pattern="[a-z0-9][a-z0-9_.-]{2,63}"
            value={username} disabled={userBusy} onChange={e => setUsername(e.target.value)} />
        </Field>
        <Pop show={!!userError}>{userError && <Alert variant="error">{userError}</Alert>}</Pop>
        <Pop show={userSaved}>{userSaved && <Alert variant="success">Login o‘zgartirildi.</Alert>}</Pop>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button type="submit" loading={userBusy} disabled={!username.trim() || unchangedUsername}>Saqlash</Button>
        </div>
      </form>

      <form onSubmit={submitPassword} className={styles.formGrid}>
        <h3 className={styles.subHeading}>Parol</h3>
        {passwordDone ? (
          <Alert variant="success">Parol o‘zgartirildi. Qayta kirishingiz kerak bo‘ladi…</Alert>
        ) : (<>
          <Field label="Joriy parol" htmlFor="profile-old-password">
            <PasswordInput id="profile-old-password" required autoComplete="current-password" value={oldPassword} disabled={passwordBusy}
              onChange={e => setOldPassword(e.target.value)} />
          </Field>
          <Field label="Yangi parol" htmlFor="profile-new-password" hint="Kamida 8 belgi.">
            <PasswordInput id="profile-new-password" required autoComplete="new-password" value={newPassword} disabled={passwordBusy}
              onChange={e => setNewPassword(e.target.value)} />
          </Field>
          <Field label="Yangi parolni takrorlang" htmlFor="profile-confirm-password">
            <PasswordInput id="profile-confirm-password" required autoComplete="new-password" value={confirmPassword} disabled={passwordBusy}
              onChange={e => setConfirmPassword(e.target.value)} />
          </Field>
          <Pop show={!!passwordError}>{passwordError && <Alert variant="error">{passwordError}</Alert>}</Pop>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button type="submit" icon={<IconKey />} loading={passwordBusy}
              disabled={!oldPassword || !newPassword || !confirmPassword}>Parolni o‘zgartirish</Button>
          </div>
        </>)}
      </form>
    </div>
  </Card>;
}

function SessionsCard() {
  const expired = useSessionExpired();
  const [data, setData] = useState<{ items: Session[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [revoking, setRevoking] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api("/auth/sessions", { signal: controller.signal })
      .then(result => { setData(result); setError(null); })
      .catch(e => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 401) expired();
        else setError(e instanceof Error ? e.message : "Sessiyalar ro‘yxati olinmadi.");
      });
    return () => controller.abort();
  }, [version, expired]);

  async function revokeOthers() {
    setRevokeBusy(true); setError(null);
    try {
      await api("/auth/sessions/revoke-others", { method: "POST" });
      setRevoking(false); setData(null); setVersion(v => v + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setError(e instanceof Error ? e.message : "Amal bajarilmadi.");
    } finally { setRevokeBusy(false); }
  }

  const otherCount = data ? data.items.filter(s => !s.is_current).length : 0;

  return <Card className={styles.section}>
    <div className={pageStyles.sectionHeading}>
      <h2>Faol sessiyalar</h2>
      {!!otherCount && <Button variant="secondary" icon={<IconLogout />} onClick={() => setRevoking(true)}>Boshqa qurilmalardan chiqish</Button>}
    </div>
    {error && <Alert variant="error">{error}</Alert>}
    {!data && !error && <div className={styles.sessionList} role="status" aria-label="Sessiyalar yuklanmoqda">
      {[0, 1].map(i => <Skeleton key={i} height="3.25rem" style={{ borderRadius: "var(--r-md)" }} />)}
    </div>}
    {data && (!data.items.length
      ? <EmptyState icon={<IconMonitor />} title="Sessiya topilmadi" description="Faol sessiya yo‘q." />
      : <div className={styles.sessionList}>
          {data.items.map((session, index) => (
            <div key={index} className={styles.sessionItem}>
              <IconMonitor />
              <div className={styles.sessionMeta}>
                <div>{new Date(session.created_at).toLocaleString("uz-UZ")}</div>
                <div className={pageStyles.muted}>Tugash: {new Date(session.expires_at).toLocaleString("uz-UZ")}</div>
              </div>
              {session.is_current && <Badge variant="accent">Joriy</Badge>}
            </div>
          ))}
        </div>)}
    <ConfirmDialog open={revoking} onClose={() => setRevoking(false)} onConfirm={revokeOthers}
      title="Boshqa qurilmalardan chiqish" confirmLabel="Chiqish" busy={revokeBusy}
      description="Joriy sessiyadan tashqari barcha sessiyalar yakunlanadi." />
  </Card>;
}
