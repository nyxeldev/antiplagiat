"use client";
import { useState } from "react";
import styles from "./page.module.css";
type Location = { kind: "page" | "paragraph"; from: number; to: number };
type Span = {
  start: number; end: number; text: string; location: Location;
  excerpt?: { before: string; after: string }; match_truncated?: boolean;
};
type Match = { method: "exact" | "shingle"; document: Span; source: Span };
type Document = { name: string; text?: string; format: string };
type CorpusMeta = {
  id: string; title: string; author_display?: string; doc_type?: string;
  year?: number | null; source_note?: string;
};
type Source = Document & {
  id: string; matched_tokens: number; coverage_percent: number; matches: Match[];
  corpus?: CorpusMeta; text_withheld?: boolean;
};
export type Report = {
  report_id: string; created_at: string; saved: boolean;
  coverage_percent: number; matched_tokens: number; token_count: number;
  document: Document; sources: Source[]; limitations: string[];
  parameters: { normalization_version: string; algorithm_version: string };
  corpus?: {
    included: boolean; retrieval_policy: string; fts_configuration: string;
    candidate_limit: number; candidates_compared: number; note: string;
  };
  excerpt_policy?: { context_chars: number; match_chars: number; report_context_budget_chars: number; note: string };
};
export const percent = (value: number) => `${value.toLocaleString("uz-UZ", { maximumFractionDigits: 2 })}%`;
function place(location: Location) { return `${location.kind === "page" ? "Sahifa" : "Paragraf"} ${location.from}${location.from === location.to ? "" : `–${location.to}`}`; }
function CorpusExcerpt({ source, span }: { source: Source; span: Span }) {
  // The corpus text itself is never sent; only this bounded excerpt is.
  const meta = source.corpus!;
  const details = [meta.author_display, meta.doc_type, meta.year ? String(meta.year) : null]
    .filter(Boolean).join(" · ");
  return <article className={styles.excerpt}>
    <h4>{meta.title} <span className={styles.corpusTag}>Ichki korpus</span></h4>
    <p className={styles.muted}>{details || "Metama’lumot ko‘rsatilmagan"}{meta.source_note ? ` · ${meta.source_note}` : ""}</p>
    <p className={styles.muted}>{place(span.location)} · belgilar [{span.start}, {span.end})</p>
    <p className={styles.text}>
      {span.excerpt?.before ? "…" : ""}{span.excerpt?.before ?? ""}
      <mark>{span.text}</mark>
      {span.excerpt?.after ?? ""}{span.excerpt?.after ? "…" : ""}
    </p>
    <p className={styles.muted}>
      {span.match_truncated ? "Mos parcha ko‘rsatish uchun qisqartirildi. " : ""}
      To‘liq korpus matni ko‘rsatilmaydi; faqat mos parcha va cheklangan kontekst beriladi.
    </p>
  </article>;
}
function Excerpt({ document, span }: { document: Document; span: Span }) {
  const points = Array.from(document.text ?? "");
  return <article className={styles.excerpt}><h4>{document.name}</h4><p className={styles.muted}>{place(span.location)} · belgilar [{span.start}, {span.end})</p>
    <p className={styles.text}>{span.start > 120 && "…"}{points.slice(Math.max(0, span.start - 120), span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end, span.end + 120).join("")}{span.end + 120 < points.length && "…"}</p>
    <details><summary>To‘liq ajratilgan matn</summary><p className={styles.text}>{points.slice(0, span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end).join("")}</p></details></article>;
}
export default function ReportView({ report }: { report: Report }) {
  const [sourceIndex, setSourceIndex] = useState(0); const [matchIndex, setMatchIndex] = useState(0);
  const source = report.sources[sourceIndex]; const match = source?.matches[matchIndex];
  return <section className={styles.panel} aria-labelledby="result-title">
    <div className={styles.sectionHeading}><h2 id="result-title">Solishtirish hisoboti</h2><span>{report.sources.length} ta manba</span></div>
    <p className={styles.muted}>Saqlangan: {new Date(report.created_at).toLocaleString("uz-UZ")}</p>
    <div className={styles.score}><strong>{percent(report.coverage_percent)}</strong><div><h3>Umumiy leksik qoplash</h3><p>{report.token_count} tokendan {report.matched_tokens} tasi mos. Ustma-ust mosliklar bir marta sanaladi.</p></div></div>
    <p className={styles.notice}>O‘xshashlik plagiatning avtomatik isboti emas.</p><h3 className={styles.subheading}>Manbani tanlang</h3>
    <div className={styles.sourceList}>{report.sources.map((item, index) => <button type="button" key={item.id} aria-pressed={sourceIndex === index} onClick={() => { setSourceIndex(index); setMatchIndex(0); }}><span>{item.name}{item.corpus && <span className={styles.corpusTag}>Ichki korpus</span>}</span><strong>{percent(item.coverage_percent)}</strong><small>{item.matches.length} ta mos parcha</small></button>)}</div>
    <p className={styles.muted}>Manba foizlari tekshirilgan hujjatga nisbatan; ular qo‘shilmaydi.</p>
    {report.corpus?.included && <p className={styles.notice}>Ichki korpusdan {report.corpus.candidates_compared} ta nomzod solishtirildi ({report.corpus.candidate_limit} limiti). Limit tufayli korpusdagi barcha hujjatlar solishtirilmagan. Nomzodlar PostgreSQL full-text qidiruvi ({report.corpus.retrieval_policy}, `{report.corpus.fts_configuration}`) bilan tanlandi; bu o‘xshashlik ko‘rsatkichi emas.</p>}
    {!source?.matches.length && <p className={styles.notice}>Ushbu manbada kamida 5 tokenli mos parcha topilmadi. Bu xulosa faqat yuklangan manbalar doirasida.</p>}
    {match && <><label className={styles.matchLabel} htmlFor="match">Mos parchani tanlang</label><select id="match" value={matchIndex} onChange={event => setMatchIndex(Number(event.target.value))}>{source.matches.map((item, index) => <option key={index} value={index}>{index + 1}. {item.method === "exact" ? "Aynan mos" : "Normallashtirilgan shingle"} · {place(item.document.location)}</option>)}</select>
      <p className={styles.muted}>{match.method === "exact" ? "Original parcha belgima-belgi teng." : "Ketma-ket normalizatsiyalangan tokenlar teng; yozilish, apostrof, bo‘shliq yoki ko‘rinmas belgilar farq qilishi mumkin."}</p><div className={styles.excerptGrid}><Excerpt document={report.document} span={match.document} />{source.corpus ? <CorpusExcerpt source={source} span={match.source} /> : <Excerpt document={source} span={match.source} />}</div></>}
    <details className={styles.limitations} open><summary>Usul va cheklovlar</summary><p>5 tokenli shingle, kamida 5 tokenli ketma-ket moslik. Unicode NFKC, registr, apostrof variantlari va lotin harflari orasidagi U+200B/U+00AD/U+200C/U+FEFF ketma-ketligi normallashtiriladi. Siyosat: {report.parameters.normalization_version}. Algoritm: {report.parameters.algorithm_version}.</p><ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>
  </section>;
}
