"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useState, type ReactNode } from "react";
import { Pop } from "../motion";
import { IconDatabase, IconHistory, IconHome, IconLogout, IconMenu, IconUpload, IconUser, IconX } from "../icons";
import { Alert, IconButton } from "../ui/primitives";
import styles from "./shell.module.css";

const NAV = [
  { href: "/", label: "Yangi tekshiruv", icon: <IconHome /> },
  { href: "/history", label: "Tekshiruvlar tarixi", icon: <IconHistory /> },
];
const CORPUS_NAV = { href: "/corpus", label: "Korpus boshqaruvi", icon: <IconDatabase /> };
const SUBMIT_NAV = { href: "/corpus/submit", label: "Korpusga hujjat taklif qilish", icon: <IconUpload /> };
export const CORPUS_MANAGEMENT_ROLES = new Set(["admin", "corpus_manager"]);

function titleFor(pathname: string) {
  if (pathname === "/") return "Yangi tekshiruv";
  if (pathname === "/history") return "Tekshiruvlar tarixi";
  if (pathname === "/corpus") return "Korpus boshqaruvi";
  if (pathname === "/corpus/submit") return "Korpusga hujjat taklif qilish";
  if (pathname.startsWith("/reports/")) return "Solishtirish hisoboti";
  return "Antiplagiat";
}

export default function AppShell({ user, onLogout, busy, error, children }: { user: { username: string; role: string; can_submit_to_corpus?: boolean }; onLogout: () => void; busy: boolean; error?: string | null; children: ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerPathname, setDrawerPathname] = useState(pathname);
  if (pathname !== drawerPathname) { setDrawerPathname(pathname); setDrawerOpen(false); }
  // A flagless "user" account never sees the submission entry, in the nav or
  // otherwise -- corpus/submit/page.tsx enforces the same check again itself,
  // since a hidden nav link is not an access control.
  const items = CORPUS_MANAGEMENT_ROLES.has(user.role) ? [...NAV, CORPUS_NAV]
    : user.role === "user" && user.can_submit_to_corpus ? [...NAV, SUBMIT_NAV] : NAV;

  const nav = (
    <>
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true">IA</span>
        <div className={styles.brandText}><strong>Islom akademiyasi</strong><span>Antiplagiat</span></div>
      </div>
      <nav className={styles.nav} aria-label="Asosiy navigatsiya">
        {items.map(item => (
          <Link key={item.href} href={item.href} className={styles.navLink} aria-current={pathname === item.href ? "page" : undefined}>
            {item.icon}{item.label}
          </Link>
        ))}
      </nav>
      <div className={styles.spacer} />
      <div className={styles.userCard}>
        <span className={styles.userAvatar} aria-hidden="true"><IconUser /></span>
        <span className={styles.userName}>{user.username}</span>
        <IconButton label="Chiqish" icon={<IconLogout />} onClick={onLogout} disabled={busy} />
      </div>
    </>
  );

  return (
    <div className={styles.layout}>
      <aside className={`${styles.sidebar} ${drawerOpen ? styles.open : ""}`} aria-label="Yon panel">{nav}</aside>
      <AnimatePresence>
        {drawerOpen && (
          <motion.div className={styles.drawerBackdrop} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }} onClick={() => setDrawerOpen(false)} />
        )}
      </AnimatePresence>
      <div className={styles.content}>
        <header className={styles.topbar}>
          <IconButton label={drawerOpen ? "Menyuni yopish" : "Menyuni ochish"} icon={drawerOpen ? <IconX /> : <IconMenu />}
            className={styles.menuToggle} onClick={() => setDrawerOpen(o => !o)} />
          <h1>{titleFor(pathname)}</h1>
        </header>
        <main className={styles.main}>
          <Pop show={!!error}>{error && <Alert variant="error">{error}</Alert>}</Pop>
          {children}
        </main>
      </div>
    </div>
  );
}
