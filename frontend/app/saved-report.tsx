"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "../lib/client-api";
import { useSessionExpired } from "./account-shell";
import ReportView, { type Report } from "./report-view";
import styles from "./page.module.css";
export default function SavedReport({ id }: { id: string }) {
  const expired = useSessionExpired(); const router = useRouter(); const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api(`/reports/${id}`, { signal: controller.signal }).then(result => { setReport(result); setError(null); }).catch(e => {
      if (controller.signal.aborted) return; if (e instanceof ApiError && e.status === 401) expired(); else { setReport(null); setError(e instanceof Error ? e.message : "Hisobot olinmadi."); }
    }); return () => controller.abort();
  }, [id, version, expired]);
  async function remove() {
    if (busy || !window.confirm("Hisobot va undagi matnlarni o‘chirasizmi?")) return; setBusy(true); setError(null);
    try { await api(`/reports/${id}`, { method: "DELETE" }); setReport(null); router.replace("/history"); }
    catch (e) { if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "O‘chirish bajarilmadi."); } finally { setBusy(false); }
  }
  return <><div className={`${styles.panel} ${styles.account}`}><Link href="/history">Tarixga qaytish</Link>{report && <button disabled={busy} onClick={remove}>Hisobotni o‘chirish</button>}</div>{error && <p role="alert" className={styles.error}>{error} <button onClick={() => { setReport(null); setVersion(version + 1); }}>Qayta urinish</button></p>}{!report && !error && <p role="status">Hisobot yuklanmoqda…</p>}{report && <ReportView key={report.report_id} report={report} />}</>;
}
