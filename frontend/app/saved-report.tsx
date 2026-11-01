"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "../lib/client-api";
import { useSessionExpired } from "./account-shell";
import { IconSearch, IconTrash } from "./icons";
import { Rise } from "./motion";
import ReportView, { type Report } from "./report-view";
import { Alert, Button, Card, EmptyState, Skeleton } from "./ui/primitives";
import { ConfirmDialog } from "./ui/Dialog";
export default function SavedReport({ id }: { id: string }) {
  const expired = useSessionExpired(); const router = useRouter(); const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null); const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false); const [version, setVersion] = useState(0); const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api(`/reports/${id}`, { signal: controller.signal }).then(result => { setReport(result); setError(null); setNotFound(false); }).catch(e => {
      if (controller.signal.aborted) return;
      if (e instanceof ApiError && e.status === 401) { expired(); return; }
      if (e instanceof ApiError && e.status === 404) { setNotFound(true); return; }
      setReport(null); setError(e instanceof Error ? e.message : "Hisobot olinmadi.");
    }); return () => controller.abort();
  }, [id, version, expired]);
  async function remove() {
    if (busy) return; setBusy(true); setError(null);
    try { await api(`/reports/${id}`, { method: "DELETE" }); setConfirming(false); setReport(null); router.replace("/history"); }
    catch (e) { if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "O‘chirish bajarilmadi."); } finally { setBusy(false); }
  }
  return <>
    <Rise><Card style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
      <Link href="/history">← Tarixga qaytish</Link>
      {report && <Button variant="destructive" icon={<IconTrash />} disabled={busy} onClick={() => setConfirming(true)}>Hisobotni o‘chirish</Button>}
    </Card></Rise>
    {error && <div style={{ marginTop: "1.5rem" }}><Alert variant="error">{error} <button onClick={() => { setReport(null); setVersion(version + 1); }} style={{ background: "none", border: 0, color: "inherit", textDecoration: "underline", cursor: "pointer", font: "inherit" }}>Qayta urinish</button></Alert></div>}
    {notFound && <Rise delay={0.05}><Card style={{ marginTop: "1.5rem" }}>
      <EmptyState icon={<IconSearch />} title="Hisobot topilmadi" description="Bu hisobot mavjud emas, o‘chirilgan yoki sizga tegishli emas." />
    </Card></Rise>}
    {!report && !error && !notFound && <Rise delay={0.05}><Card style={{ marginTop: "1.5rem" }}><Skeleton height="2.5rem" style={{ marginBottom: "1rem" }} /><Skeleton height="8rem" /></Card></Rise>}
    {report && <Rise delay={0.08}><div style={{ marginTop: "1.5rem" }}><ReportView key={report.report_id} report={report} /></div></Rise>}
    <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} onConfirm={remove} busy={busy}
      title="Hisobotni o‘chirish" confirmLabel="O‘chirish" description="Hisobot va undagi matnlar butunlay o‘chiriladi. Bu amalni qaytarib bo‘lmaydi." />
  </>;
}
