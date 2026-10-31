"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useSessionExpired } from "../account-shell";
import { IconHistory, IconTrash } from "../icons";
import { EASE_OUT, Rise } from "../motion";
import { percent } from "../report-view";
import { Alert, Badge, Card, EmptyState, IconButton, Pagination, Skeleton } from "../ui/primitives";
import { ConfirmDialog } from "../ui/Dialog";
import styles from "./history.module.css";
import pageStyles from "../page.module.css";
type Item = { id: string; name: string; created_at: string; coverage_percent: number };
export default function History() {
  const expired = useSessionExpired(); const [page, setPage] = useState(1); const [version, setVersion] = useState(0);
  const [data, setData] = useState<{ items: Item[]; has_next: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null); const [deleting, setDeleting] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Item | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api(`/reports?page=${page}`, { signal: controller.signal }).then(result => { setData(result); setError(null); }).catch(e => {
      if (controller.signal.aborted) return; if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Tarix olinmadi.");
    }); return () => controller.abort();
  }, [page, version, expired]);
  async function remove(item: Item) {
    setDeleting(item.id); setError(null);
    try { await api(`/reports/${item.id}`, { method: "DELETE" }); setConfirming(null); setData(null); if (data?.items.length === 1 && page > 1) setPage(page - 1); else setVersion(version + 1); }
    catch (e) { if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "O‘chirish bajarilmadi."); } finally { setDeleting(null); }
  }
  return <Rise><Card>
    <h2>Tekshiruvlar tarixi</h2>
    <p className={pageStyles.muted}>Faqat o‘zingizning saqlangan hisobotlaringiz. Original binar fayllar saqlanmaydi.</p>
    <div style={{ marginTop: "var(--sp-5)" }}>
      {error && <Alert variant="error">{error} <button onClick={() => { setData(null); setVersion(version + 1); }} style={{ background: "none", border: 0, color: "inherit", textDecoration: "underline", cursor: "pointer", font: "inherit" }}>Qayta urinish</button></Alert>}
      {!data && !error && <div className={styles.table} role="status" aria-label="Tarix yuklanmoqda">
        {[0, 1, 2].map(i => <Skeleton key={i} height="4.25rem" style={{ borderRadius: "var(--r-md)" }} />)}
      </div>}
      {data && <>
        {!data.items.length
          ? <EmptyState icon={<IconHistory />} title="Saqlangan tekshiruvlar yo‘q" description="Yangi tekshiruv boshlab, natija bu yerda paydo bo‘ladi." />
          : <div className={styles.table}>
              <div className={styles.headerRow}><span>Hujjat</span><span>Sana</span><span>Natija</span><span /></div>
              <AnimatePresence initial={false}>
                {data.items.map((item, index) => <motion.div key={item.id} layout className={styles.row}
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -24 }}
                  transition={{ duration: 0.3, delay: index * 0.04, ease: EASE_OUT }}>
                  <Link href={`/reports/${item.id}`} className={styles.name}>{item.name}</Link>
                  <span className={styles.date}>{new Date(item.created_at).toLocaleString("uz-UZ")}</span>
                  <Badge variant="accent">{percent(item.coverage_percent)}</Badge>
                  <IconButton label={`“${item.name}” hisobotini o‘chirish`} icon={<IconTrash />} disabled={!!deleting} onClick={() => setConfirming(item)} />
                </motion.div>)}
              </AnimatePresence>
            </div>}
        {data.items.length > 0 && <Pagination page={page} hasNext={data.has_next} disabled={!!deleting} onChange={next => { setData(null); setPage(next); }} />}
      </>}
    </div>
    <ConfirmDialog open={!!confirming} onClose={() => setConfirming(null)} onConfirm={() => confirming && remove(confirming)}
      title="Hisobotni o‘chirish" confirmLabel="O‘chirish" busy={!!deleting}
      description={confirming && <>“{confirming.name}” hisoboti va undagi matnlar butunlay o‘chiriladi. Bu amalni qaytarib bo‘lmaydi.</>} />
  </Card></Rise>;
}
