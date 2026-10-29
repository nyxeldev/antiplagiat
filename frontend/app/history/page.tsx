"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useSessionExpired } from "../account-shell";
import { EASE_OUT, Rise, tap } from "../motion";
import { percent } from "../report-view";
import styles from "../page.module.css";
type Item = { id: string; name: string; created_at: string; coverage_percent: number };
export default function History() {
  const expired = useSessionExpired(); const [page, setPage] = useState(1); const [version, setVersion] = useState(0);
  const [data, setData] = useState<{ items: Item[]; has_next: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null); const [deleting, setDeleting] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api(`/reports?page=${page}`, { signal: controller.signal }).then(result => { setData(result); setError(null); }).catch(e => {
      if (controller.signal.aborted) return; if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Tarix olinmadi.");
    }); return () => controller.abort();
  }, [page, version, expired]);
  async function remove(item: Item) {
    if (deleting || !window.confirm(`“${item.name}” hisoboti va undagi matnlarni o‘chirasizmi?`)) return; setDeleting(item.id); setError(null);
    try { await api(`/reports/${item.id}`, { method: "DELETE" }); setData(null); if (data?.items.length === 1 && page > 1) setPage(page - 1); else setVersion(version + 1); }
    catch (e) { if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "O‘chirish bajarilmadi."); } finally { setDeleting(null); }
  }
  return <Rise><section className={styles.panel}><h2>Tekshiruvlar tarixi</h2><p className={styles.muted}>Faqat o‘zingizning saqlangan hisobotlaringiz. Original binar fayllar saqlanmaydi.</p>
    {error && <p role="alert" className={styles.error}>{error} <button onClick={() => { setData(null); setVersion(version + 1); }}>Qayta urinish</button></p>}{!data && !error && <p role="status">Tarix yuklanmoqda…</p>}
    {data && <>{!data.items.length && <p className={styles.muted}>Saqlangan tekshiruvlar yo‘q.</p>}
      <ul className={styles.history}>
        <AnimatePresence initial={false}>
          {data.items.map((item, index) => <motion.li key={item.id} layout
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.3, delay: index * 0.04, ease: EASE_OUT }}>
            <div><Link href={`/reports/${item.id}`}>{item.name}</Link><p className={styles.muted}>{new Date(item.created_at).toLocaleString("uz-UZ")} · {percent(item.coverage_percent)}</p></div>
            <motion.button whileTap={tap} disabled={!!deleting} onClick={() => remove(item)}>O‘chirish</motion.button>
          </motion.li>)}
        </AnimatePresence>
      </ul>
      <div className={styles.account}><motion.button whileTap={tap} disabled={page <= 1 || !!deleting} onClick={() => { setData(null); setPage(page - 1); }}>Oldingi</motion.button><span>{page}-sahifa</span><motion.button whileTap={tap} disabled={!data.has_next || !!deleting} onClick={() => { setData(null); setPage(page + 1); }}>Keyingi</motion.button></div></>}
  </section></Rise>;
}
