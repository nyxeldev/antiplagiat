"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/client-api";
import { useSessionExpired } from "./account-shell";
import { IconDatabase, IconSparkle } from "./icons";
import { Disclosure, EASE_OUT, Pop, Rise } from "./motion";
import ReportView, { type Report } from "./report-view";
import { Alert, Button, Card } from "./ui/primitives";
import { Dropzone, StepBadge } from "./ui/Dropzone";
import { FileItem } from "./ui/FileItem";
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
  const [includeCorpus, setIncludeCorpus] = useState(true);
  const [morphAware, setMorphAware] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const [report, setReport] = useState<Report | null>(null);
  function resetResult() { key.current = null; setReport(null); setError(null); }
  function addDocument(files: File[]) {
    const file = files[0]; if (!file) return;
    const problem = fileError([file, ...sources]); if (problem) setError(problem); else { resetResult(); setDocument(file); }
  }
  function addSources(files: File[]) {
    const next = [...sources, ...files];
    const problem = next.length > 5 ? "Ko‘pi bilan 5 ta manba tanlang." : fileError([...(document ? [document] : []), ...next]);
    if (problem) setError(problem); else { resetResult(); setSources(next); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!document || (!sources.length && !includeCorpus) || inFlight.current) return;
    const validation = fileError([document, ...sources]); if (validation) { setError(validation); return; }
    inFlight.current = true; setBusy(true); setError(null); setReport(null); key.current ??= crypto.randomUUID();
    const data = new FormData(); data.append("document", document); sources.forEach(source => data.append("sources", source));
    try {
      const params = includeCorpus
        ? `?include_corpus=true${morphAware ? "&normalization=v3-matching" : ""}` : "";
      const path = `/compare${params}`;
      const result = await api(path, { method: "POST", body: data, headers: { "Idempotency-Key": key.current }, signal: AbortSignal.timeout(100_000) });
      if (!result.saved || !result.report_id) throw new Error("Hisobot saqlanganligi tasdiqlanmadi.");
      setReport(result);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) expired();
      else setError(reason instanceof Error && reason.name !== "TimeoutError" ? reason.message : "Vaqt tugadi. Tarixni tekshiring yoki shu fayllar bilan qayta urinib ko‘ring.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <><Rise><Card><form onSubmit={submit} aria-busy={busy}>
    <div className={styles.sectionHeading}><h2>Yangi tekshiruv</h2><span>Lokal prototip</span></div>
    <p className={styles.muted} id="upload-help">UTF-8 TXT, DOCX yoki matn qatlamli PDF. Har fayl 10 MiB gacha, jami 30 MiB. Har hujjatda kamida 5 ta so‘z/son bo‘lsin.</p>

    <div style={{ marginTop: "var(--sp-6)" }}>
      <StepBadge step={1}>Tekshiriladigan hujjat</StepBadge>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className={styles.srOnly}>Tekshiriladigan hujjat</legend>
        {!document && <Dropzone label="Fayl tanlash yoki shu yerga tashlang" hint="TXT, DOCX yoki PDF — 10 MiB gacha"
          accept={accept} describedBy="upload-help" onFiles={addDocument} />}
        <AnimatePresence initial={false}>
          {document && <motion.div key={document.name} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.2, ease: EASE_OUT }}>
            <FileItem name={document.name} size={document.size} removeLabel={`${document.name} hujjatini olib tashlash`} onRemove={() => { setDocument(null); resetResult(); }} />
          </motion.div>}
        </AnimatePresence>
      </fieldset>
    </div>

    <div style={{ marginTop: "var(--sp-8)" }}>
      <StepBadge step={2}>Solishtirish manbalari</StepBadge>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
        <legend className={styles.srOnly}>Manba hujjatlar va ichki korpus</legend>

        <Card pad={false} style={{ padding: "var(--sp-4)" }}>
          <label className={styles.corpusOption} htmlFor="include-corpus">
            <input id="include-corpus" type="checkbox" checked={includeCorpus} disabled={busy}
              onChange={event => { setIncludeCorpus(event.target.checked); resetResult(); }} />
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}><IconDatabase style={{ width: "1.05rem", height: "1.05rem" }} />Ichki korpus bo‘yicha tekshirish</span>
          </label>
          <p className={styles.muted}>Birlamchi usul: akademiyaning ruxsat asosida saqlangan ichki korpusidan nomzod manbalar avtomatik tanlanadi. Korpus manbasidan faqat mos parcha va qisqa kontekst ko‘rsatiladi; to‘liq matn berilmaydi. Limit tufayli korpusdagi barcha hujjatlar solishtirilmaydi.</p>
          <Pop show={includeCorpus}>
            <label className={styles.corpusOption} htmlFor="morph-aware">
              <input id="morph-aware" type="checkbox" checked={morphAware} disabled={busy}
                onChange={event => { setMorphAware(event.target.checked); resetResult(); }} />
              <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}><IconSparkle style={{ width: "1.05rem", height: "1.05rem" }} />O‘zbekcha qo‘shimchalarni hisobga olish (tajriba)</span>
            </label>
            <p className={styles.muted}>Qoidaga asoslangan, lug‘atsiz usul bilan o‘zbekcha so‘z qo‘shimchalarini (masalan “-lar”, “-ning”, “-dan”) tanib, nomzod manbalarni HAM, mos parchani belgilashni HAM shu holatni hisobga olib bajaradi: masalan “kitoblarni” va “kitobni” endi mos deb belgilanishi mumkin. Ko‘rsatilgan foiz shu sabab alohida, tajriba xususiyatiga ega siyosat (lexical-shingle-v2) bilan hisoblanadi — standart (bu belgisiz) natijalar bilan solishtirilmaydi.</p>
          </Pop>
        </Card>

        <Disclosure defaultOpen={sources.length > 0}
          summary={<>Qo‘shimcha manba qo‘shish (qo‘lda yuklash){sources.length > 0 ? ` — ${sources.length} ta tanlangan` : ""}</>}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)", marginTop: "var(--sp-3)" }}>
            <p className={styles.muted} style={{ marginTop: 0 }}>Ichki korpusga qo‘shilmagan yoki alohida solishtirish kerak bo‘lgan manbalarni shu yerdan qo‘lda yuklang.</p>
            <AnimatePresence initial={false}>
              {sources.map((file, index) => <motion.div key={`${index}-${file.name}`} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.2, ease: EASE_OUT }}>
                <FileItem name={file.name} size={file.size} removeLabel={`${file.name} manbasini olib tashlash`}
                  onRemove={() => { setSources(sources.filter((_, i) => i !== index)); resetResult(); }} />
              </motion.div>)}
            </AnimatePresence>
            {sources.length < 5 && <Dropzone label={`Manba qo‘shish (${sources.length}/5)`} hint="Bir nechtasini birdan tanlash mumkin"
              accept={accept} multiple describedBy="upload-help" onFiles={addSources} />}
          </div>
        </Disclosure>
      </fieldset>
    </div>

    <Alert variant="info" compact={false}>Muvaffaqiyatli hisobot, shu jumladan ajratilgan hujjat va manba matnlari shaxsiy tarixingizda saqlanadi. Binar fayllar saqlanmaydi; umumiy korpusga qo‘shilmaydi va internetga yuborilmaydi.</Alert>

    <div style={{ marginTop: "var(--sp-8)" }}>
      <StepBadge step={3}>Tekshiruvni boshlash</StepBadge>
      <Button type="submit" loading={busy} disabled={!document || (!sources.length && !includeCorpus)}>{busy ? "Solishtirilmoqda…" : "Solishtirish"}</Button>
      <p role="status" className={styles.muted} style={{ marginTop: "var(--sp-3)" }}>
        {busy ? "Fayllar yuklanmoqda, solishtirilmoqda va hisobot saqlanmoqda…"
          : report ? "Hisobot shaxsiy tarixingizga saqlandi."
          : document && !sources.length && !includeCorpus ? "Solishtirish uchun kamida bitta manba fayl yuklang yoki ichki korpusni yoqing."
          : ""}
      </p>
      <Pop show={!!report}>
        {report && <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          <Link href={`/reports/${report.report_id}`}>Saqlangan hisobotni ochish</Link>
          <Button type="button" variant="secondary" onClick={() => { setDocument(null); setSources([]); resetResult(); }}>Yangi tekshiruv boshlash</Button>
        </div>}
      </Pop>
      <Pop show={!!error}>{error && <Alert variant="error">{error}</Alert>}</Pop>
    </div>
  </form></Card></Rise>{report && <Rise delay={0.08}><ReportView key={report.report_id} report={report} /></Rise>}</>;
}
