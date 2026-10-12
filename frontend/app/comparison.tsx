"use client";

import { useState, type FormEvent } from "react";
import styles from "./page.module.css";

type Location = { kind: "page" | "paragraph"; from: number; to: number };
type Span = { start: number; end: number; text: string; location: Location };
type Match = { method: "exact" | "shingle"; document: Span; source: Span };
type Document = { name: string; text: string; format: string };
type Source = Document & { id: string; matched_tokens: number; coverage_percent: number; matches: Match[] };
type Report = {
  coverage_percent: number; matched_tokens: number; token_count: number;
  document: Document; sources: Source[]; limitations: string[];
  parameters: { normalization_version: string };
};
const MIB = 1024 * 1024;
const accept = ".txt,.docx,.pdf";
const percent = (value: number) => `${value.toLocaleString("uz-UZ", { maximumFractionDigits: 2 })}%`;

function fileError(files: File[]) {
  if (files.some(file => !/\.(txt|docx|pdf)$/i.test(file.name))) return "Faqat TXT, DOCX yoki PDF tanlang.";
  if (files.some(file => !file.size)) return "Bo‘sh faylni solishtirib bo‘lmaydi.";
  if (files.some(file => file.size > 10 * MIB)) return "Bitta fayl hajmi 10 MiB dan oshmasin.";
  if (files.reduce((sum, file) => sum + file.size, 0) > 30 * MIB) return "Jami fayllar hajmi 30 MiB dan oshmasin.";
  return null;
}
function place(location: Location) {
  return `${location.kind === "page" ? "Sahifa" : "Paragraf"} ${location.from}${location.from === location.to ? "" : `–${location.to}`}`;
}
function Excerpt({ document, span }: { document: Document; span: Span }) {
  // API offsets count Unicode code points; JS string.slice counts UTF-16 units.
  const points = Array.from(document.text);
  return <article className={styles.excerpt}>
    <h4>{document.name}</h4>
    <p className={styles.muted}>{place(span.location)} · belgilar [{span.start}, {span.end})</p>
    <p className={styles.text}>
      {span.start > 120 && "…"}{points.slice(Math.max(0, span.start - 120), span.start).join("")}
      <mark>{points.slice(span.start, span.end).join("")}</mark>
      {points.slice(span.end, span.end + 120).join("")}{span.end + 120 < points.length && "…"}
    </p>
    <details><summary>To‘liq ajratilgan matn</summary>
      <p className={styles.text}>{points.slice(0, span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end).join("")}</p>
    </details>
  </article>;
}

export default function Comparison() {
  const [document, setDocument] = useState<File | null>(null);
  const [sources, setSources] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [sourceIndex, setSourceIndex] = useState(0);
  const [matchIndex, setMatchIndex] = useState(0);
  function resetResult() { setReport(null); setError(null); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!document || !sources.length || busy) return;
    const validation = fileError([document, ...sources]);
    if (validation) { setError(validation); return; }
    setBusy(true); setError(null); setReport(null);
    const data = new FormData();
    data.append("document", document);
    sources.forEach(source => data.append("sources", source));
    try {
      const response = await fetch("/api/compare", {
        method: "POST", body: data, headers: { "X-Antiplagiat-Local": "1" },
        signal: AbortSignal.timeout(100_000),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = result.error;
        throw new Error(`${detail?.file ? `${detail.file}: ` : ""}${detail?.message ?? "Tekshiruv bajarilmadi."}`);
      }
      setReport(result); setSourceIndex(0); setMatchIndex(0);
    } catch (reason) {
      setError(reason instanceof Error && reason.name !== "TimeoutError" ? reason.message : "Tekshiruv vaqti tugadi. Qayta urinib ko‘ring.");
    } finally { setBusy(false); }
  }
  const source = report?.sources[sourceIndex];
  const match = source?.matches[matchIndex];
  return <>
    <form onSubmit={submit} className={styles.panel} aria-busy={busy}>
      <div className={styles.sectionHeading}><h2>Hujjatlarni solishtirish</h2><span>Lokal prototip</span></div>
      <p className={styles.muted} id="upload-help">UTF-8 TXT, DOCX yoki matn qatlamli PDF. Har fayl 10 MiB gacha, jami 30 MiB. Har hujjatda kamida 5 ta so‘z/son bo‘lsin.</p>
      <fieldset disabled={busy} className={styles.uploadGrid}>
        <legend className={styles.srOnly}>Tekshiriladigan hujjat va manbalar</legend>
        <div className={styles.uploadBox}>
          <label htmlFor="document">1. Tekshiriladigan hujjat</label>
          <input id="document" type="file" accept={accept} aria-describedby="upload-help" onChange={event => {
            const file = event.target.files?.[0]; event.target.value = "";
            if (!file) return;
            resetResult(); const problem = fileError([file, ...sources]);
            if (problem) setError(problem); else setDocument(file);
          }} />
          {document && <div className={styles.file}><span>{document.name}<small>{(document.size / MIB).toFixed(2)} MiB</small></span>
            <button type="button" onClick={() => { setDocument(null); resetResult(); }} aria-label={`${document.name} hujjatini olib tashlash`}>Olib tashlash</button></div>}
        </div>
        <div className={styles.uploadBox}>
          <label htmlFor="sources">2. Manba hujjatlar ({sources.length}/5)</label>
          <input id="sources" type="file" accept={accept} multiple aria-describedby="upload-help" onChange={event => {
            const files = Array.from(event.target.files ?? []); event.target.value = "";
            if (!files.length) return;
            resetResult(); const next = [...sources, ...files];
            const problem = next.length > 5 ? "Ko‘pi bilan 5 ta manba tanlang." : fileError([...(document ? [document] : []), ...next]);
            if (problem) setError(problem); else setSources(next);
          }} />
          {sources.map((file, index) => <div className={styles.file} key={`${index}-${file.name}`}>
            <span>{file.name}<small>{(file.size / MIB).toFixed(2)} MiB</small></span>
            <button type="button" aria-label={`${file.name} manbasini olib tashlash`} onClick={() => { setSources(sources.filter((_, i) => i !== index)); resetResult(); }}>Olib tashlash</button>
          </div>)}
        </div>
      </fieldset>
      <p className={styles.muted}>Fayllar faqat shu tekshiruvda ishlatiladi. Doimiy korpusga saqlanmaydi va internetga yuborilmaydi.</p>
      <button className={styles.primary} disabled={busy || !document || sources.length < 1} type="submit">{busy ? "Solishtirilmoqda…" : "Solishtirish"}</button>
      <p role="status" className={styles.muted}>{busy ? "Fayllar yuklanmoqda va matnlar solishtirilmoqda. Kuting…" : report ? "Tekshiruv yakunlandi." : ""}</p>
      {error && <p role="alert" className={styles.error}>{error}</p>}
    </form>
    {report && <section className={styles.panel} aria-labelledby="result-title">
      <div className={styles.sectionHeading}><h2 id="result-title">Solishtirish hisoboti</h2><span>{report.sources.length} ta manba</span></div>
      <div className={styles.score}><strong>{percent(report.coverage_percent)}</strong><div><h3>Umumiy leksik qoplash</h3><p>{report.token_count} tokendan {report.matched_tokens} tasi mos. Ustma-ust mosliklar bir marta sanaladi.</p></div></div>
      <p className={styles.notice}>O‘xshashlik plagiatning avtomatik isboti emas.</p>
      <h3 className={styles.subheading}>Manbani tanlang</h3>
      <div className={styles.sourceList}>{report.sources.map((item, index) => <button type="button" key={item.id} aria-pressed={sourceIndex === index} onClick={() => { setSourceIndex(index); setMatchIndex(0); }}>
        <span>{item.name}</span><strong>{percent(item.coverage_percent)}</strong><small>{item.matches.length} ta mos parcha</small>
      </button>)}</div>
      <p className={styles.muted}>Manba foizlari tekshirilgan hujjatga nisbatan; ular qo‘shilmaydi.</p>
      {source && !source.matches.length && <p className={styles.notice}>Ushbu manbada kamida 5 tokenli mos parcha topilmadi. Bu xulosa faqat yuklangan manbalar doirasida.</p>}
      {source && match && <>
        <label className={styles.matchLabel} htmlFor="match">Mos parchani tanlang</label>
        <select id="match" value={matchIndex} onChange={event => setMatchIndex(Number(event.target.value))}>
          {source.matches.map((item, index) => <option key={index} value={index}>{index + 1}. {item.method === "exact" ? "Aynan mos" : "Normallashtirilgan shingle"} · {place(item.document.location)}</option>)}
        </select>
        <p className={styles.muted}>{match.method === "exact" ? "Original parcha belgima-belgi teng." : "Ketma-ket normalizatsiyalangan tokenlar teng; yozilish, apostrof, bo‘shliq yoki ko‘rinmas belgilar farq qilishi mumkin."}</p>
        <div className={styles.excerptGrid}><Excerpt document={report.document} span={match.document} /><Excerpt document={source} span={match.source} /></div>
      </>}
      <details className={styles.limitations} open><summary>Usul va cheklovlar</summary>
        <p>5 tokenli shingle, kamida 5 tokenli ketma-ket moslik. Unicode NFKC, registr, apostrof variantlari va lotin harflari orasidagi U+200B/U+00AD/U+200C/U+FEFF ketma-ketligi normallashtiriladi. Siyosat: {report.parameters.normalization_version}.</p>
        <ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul>
      </details>
    </section>}
  </>;
}
