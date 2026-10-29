"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/client-api";
import { useSessionExpired } from "./account-shell";
import { EASE_OUT, Pop, Rise, tap } from "./motion";
import ReportView, { type Report } from "./report-view";
import styles from "./page.module.css";
const MIB = 1024 * 1024;
const accept = ".txt,.docx,.pdf";
function fileError(files: File[]) {
  if (files.some(file => !/\.(txt|docx|pdf)$/i.test(file.name))) return "Faqat TXT, DOCX yoki PDF tanlang.";
  if (files.some(file => !file.size)) return "Bo‘sh faylni solishtirib bo‘lmaydi.";
  if (files.some(file => file.size > 10 * MIB)) return "Bitta fayl hajmi 10 MiB dan oshmasin.";
  if (files.reduce((sum, file) => sum + file.size, 0) > 30 * MIB) return "Jami fayllar hajmi 30 MiB dan oshmasin.";
  return null;
}
export default function Comparison() {
  const expired = useSessionExpired(); const key = useRef<string | null>(null); const inFlight = useRef(false);
  const [document, setDocument] = useState<File | null>(null); const [sources, setSources] = useState<File[]>([]);
  const [includeCorpus, setIncludeCorpus] = useState(false);
  const [morphAware, setMorphAware] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const [report, setReport] = useState<Report | null>(null);
  function resetResult() { key.current = null; setReport(null); setError(null); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!document || !sources.length || inFlight.current) return;
    const validation = fileError([document, ...sources]); if (validation) { setError(validation); return; }
    inFlight.current = true; setBusy(true); setError(null); setReport(null); key.current ??= crypto.randomUUID();
    const data = new FormData(); data.append("document", document); sources.forEach(source => data.append("sources", source));
    try {
      const params = includeCorpus
        ? `?include_corpus=true${morphAware ? "&normalization=v3" : ""}` : "";
      const path = `/compare${params}`;
      const result = await api(path, { method: "POST", body: data, headers: { "Idempotency-Key": key.current }, signal: AbortSignal.timeout(100_000) });
      if (!result.saved || !result.report_id) throw new Error("Hisobot saqlanganligi tasdiqlanmadi.");
      setReport(result);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) expired();
      else setError(reason instanceof Error && reason.name !== "TimeoutError" ? reason.message : "Vaqt tugadi. Tarixni tekshiring yoki shu fayllar bilan qayta urinib ko‘ring.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <><Rise><form onSubmit={submit} className={styles.panel} aria-busy={busy}>
    <div className={styles.sectionHeading}><h2>Hujjatlarni solishtirish</h2><span>Lokal prototip</span></div>
    <p className={styles.muted} id="upload-help">UTF-8 TXT, DOCX yoki matn qatlamli PDF. Har fayl 10 MiB gacha, jami 30 MiB. Har hujjatda kamida 5 ta so‘z/son bo‘lsin.</p>
    <fieldset disabled={busy} className={styles.uploadGrid}><legend className={styles.srOnly}>Tekshiriladigan hujjat va manbalar</legend>
      <div className={styles.uploadBox}><label htmlFor="document">1. Tekshiriladigan hujjat</label><input id="document" type="file" accept={accept} aria-describedby="upload-help" onChange={event => {
        const file = event.target.files?.[0]; event.target.value = ""; if (!file) return;
        const problem = fileError([file, ...sources]); if (problem) setError(problem); else { resetResult(); setDocument(file); }
      }} />
        <AnimatePresence initial={false}>
          {document && <motion.div key={document.name} className={styles.file}
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.2, ease: EASE_OUT }}>
            <span>{document.name}<small>{(document.size / MIB).toFixed(2)} MiB</small></span>
            <button type="button" onClick={() => { setDocument(null); resetResult(); }} aria-label={`${document.name} hujjatini olib tashlash`}>Olib tashlash</button>
          </motion.div>}
        </AnimatePresence>
      </div>
      <div className={styles.uploadBox}><label htmlFor="sources">2. Manba hujjatlar ({sources.length}/5)</label><input id="sources" type="file" accept={accept} multiple aria-describedby="upload-help" onChange={event => {
        const files = Array.from(event.target.files ?? []); event.target.value = ""; if (!files.length) return;
        const next = [...sources, ...files]; const problem = next.length > 5 ? "Ko‘pi bilan 5 ta manba tanlang." : fileError([...(document ? [document] : []), ...next]);
        if (problem) setError(problem); else { resetResult(); setSources(next); }
      }} />
        <AnimatePresence initial={false}>
          {sources.map((file, index) => <motion.div className={styles.file} key={`${index}-${file.name}`}
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.2, ease: EASE_OUT }}>
            <span>{file.name}<small>{(file.size / MIB).toFixed(2)} MiB</small></span>
            <button type="button" aria-label={`${file.name} manbasini olib tashlash`} onClick={() => { setSources(sources.filter((_, i) => i !== index)); resetResult(); }}>Olib tashlash</button>
          </motion.div>)}
        </AnimatePresence>
      </div>
    </fieldset>
    <div className={styles.uploadBox}>
      <label className={styles.corpusOption} htmlFor="include-corpus">
        <input id="include-corpus" type="checkbox" checked={includeCorpus} disabled={busy}
          onChange={event => { setIncludeCorpus(event.target.checked); resetResult(); }} />
        <span>Ichki korpus bo‘yicha ham tekshirish</span>
      </label>
      <p className={styles.muted}>Qo‘shimcha ravishda akademiyaning ruxsat asosida saqlangan ichki korpusidan nomzod manbalar tanlanadi. Korpus manbasidan faqat mos parcha va qisqa kontekst ko‘rsatiladi; to‘liq matn berilmaydi. Limit tufayli korpusdagi barcha hujjatlar solishtirilmaydi.</p>
      <Pop show={includeCorpus}>
        <label className={styles.corpusOption} htmlFor="morph-aware">
          <input id="morph-aware" type="checkbox" checked={morphAware} disabled={busy}
            onChange={event => { setMorphAware(event.target.checked); resetResult(); }} />
          <span>O‘zbekcha qo‘shimchalarni hisobga olish (tajriba)</span>
        </label>
        <p className={styles.muted}>Qoidaga asoslangan, lug‘atsiz usul bilan o‘zbekcha so‘z qo‘shimchalarini (masalan “-lar”, “-ning”, “-dan”) tanib, nomzod manbalarni shu holatni hisobga olib qidiradi. Faqat qaysi hujjatlar nomzod sifatida tanlanishiga ta’sir qiladi; mos parchani belgilash hamon o‘zgarmagan algoritmda.</p>
      </Pop>
    </div>
    <p className={styles.notice}>Muvaffaqiyatli hisobot, shu jumladan ajratilgan hujjat va manba matnlari shaxsiy tarixingizda saqlanadi. Binar fayllar saqlanmaydi; umumiy korpusga qo‘shilmaydi va internetga yuborilmaydi.</p>
    <motion.button whileTap={tap} className={styles.primary} disabled={busy || !document || !sources.length} type="submit">
      {busy && <span className={styles.spinner} aria-hidden="true" />}{busy ? "Solishtirilmoqda…" : "Solishtirish"}
    </motion.button>
    <p role="status" className={styles.muted}>{busy ? "Fayllar yuklanmoqda, solishtirilmoqda va hisobot saqlanmoqda…" : report ? "Hisobot shaxsiy tarixingizga saqlandi." : ""}</p>
    <Pop show={!!report}>
      {report && <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
        <Link href={`/reports/${report.report_id}`}>Saqlangan hisobotni ochish</Link>
        <motion.button whileTap={tap} type="button" className={styles.primary} onClick={() => { setDocument(null); setSources([]); resetResult(); }}>Yangi tekshiruv boshlash</motion.button>
      </div>}
    </Pop>
    <Pop show={!!error}>{error && <p role="alert" className={styles.error}>{error}</p>}</Pop>
  </form></Rise>{report && <Rise delay={0.08}><ReportView key={report.report_id} report={report} /></Rise>}</>;
}
