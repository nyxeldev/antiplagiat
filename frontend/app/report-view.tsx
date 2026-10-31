"use client";
import { useState } from "react";
import { Crossfade, Disclosure, Stagger, StaggerItem } from "./motion";
import { useMediaQuery } from "./use-media-query";
import { Alert, Badge, Select } from "./ui/primitives";
import { Metric } from "./ui/Metric";
import { Tabs } from "./ui/Tabs";
import { IconDatabase } from "./icons";
import reportStyles from "./report.module.css";
import pageStyles from "./page.module.css";
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
    candidate_limit: number; candidates_compared: number; note: string; normalization?: string;
  };
  excerpt_policy?: { context_chars: number; match_chars: number; report_context_budget_chars: number; note: string };
};
export const percent = (value: number) => `${value.toLocaleString("uz-UZ", { maximumFractionDigits: 2 })}%`;
function place(location: Location) { return `${location.kind === "page" ? "Sahifa" : "Paragraf"} ${location.from}${location.from === location.to ? "" : `–${location.to}`}`; }

function CorpusExcerpt({ source, span }: { source: Source; span: Span }) {
  // The corpus text itself is never sent; only this bounded excerpt is.
  const meta = source.corpus!;
  const details = [meta.author_display, meta.doc_type, meta.year ? String(meta.year) : null].filter(Boolean).join(" · ");
  return <article className={reportStyles.excerpt}>
    <div className={reportStyles.excerptHead}><h4>{meta.title} <Badge variant="accent" onLight icon={<IconDatabase />}>Ichki korpus</Badge></h4></div>
    <div className={reportStyles.excerptBody}>
      <p className={pageStyles.muted}>{details || "Metama’lumot ko‘rsatilmagan"}{meta.source_note ? ` · ${meta.source_note}` : ""}</p>
      <p className={pageStyles.muted}>{place(span.location)} · belgilar [{span.start}, {span.end})</p>
      <p className={reportStyles.text}>
        {span.excerpt?.before ? "…" : ""}{span.excerpt?.before ?? ""}
        <mark>{span.text}</mark>
        {span.excerpt?.after ?? ""}{span.excerpt?.after ? "…" : ""}
      </p>
      <p className={pageStyles.muted}>
        {span.match_truncated ? "Mos parcha ko‘rsatish uchun qisqartirildi. " : ""}
        To‘liq korpus matni ko‘rsatilmaydi; faqat mos parcha va cheklangan kontekst beriladi.
      </p>
    </div>
  </article>;
}
function Excerpt({ document, span }: { document: Document; span: Span }) {
  const points = Array.from(document.text ?? "");
  return <article className={reportStyles.excerpt}>
    <div className={reportStyles.excerptHead}><h4>{document.name}</h4></div>
    <div className={reportStyles.excerptBody}>
      <p className={pageStyles.muted}>{place(span.location)} · belgilar [{span.start}, {span.end})</p>
      <p className={reportStyles.text}>{span.start > 120 && "…"}{points.slice(Math.max(0, span.start - 120), span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end, span.end + 120).join("")}{span.end + 120 < points.length && "…"}</p>
      <Disclosure summary="To‘liq ajratilgan matn" summaryClassName={reportStyles.disclosureSummary}>
        <p className={reportStyles.text} style={{ marginTop: "var(--sp-3)" }}>{points.slice(0, span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end).join("")}</p>
      </Disclosure>
    </div>
  </article>;
}

export default function ReportView({ report }: { report: Report }) {
  const [sourceIndex, setSourceIndex] = useState(0); const [matchIndex, setMatchIndex] = useState(0);
  const [mobilePane, setMobilePane] = useState<"document" | "source">("document");
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const source = report.sources[sourceIndex]; const match = source?.matches[matchIndex];

  const sourcePanel = match && (source.corpus
    ? <CorpusExcerpt source={source} span={match.source} />
    : <Excerpt document={source} span={match.source} />);
  const documentPanel = match && <Excerpt document={report.document} span={match.document} />;

  return <section className={reportStyles.sheet} aria-labelledby="result-title" data-surface="light">
    <div className={reportStyles.sheetHead}>
      <div className={pageStyles.sectionHeading} style={{ marginBottom: 0 }}>
        <h2 id="result-title" style={{ color: "var(--ink-on-light)" }}>Solishtirish hisoboti</h2>
        <Badge variant="neutral" onLight>{report.sources.length} ta manba</Badge>
      </div>
      <p className={reportStyles.meta}>Saqlangan: {new Date(report.created_at).toLocaleString("uz-UZ")}</p>
      <div style={{ marginTop: "var(--sp-6)" }}>
        <Metric value={report.coverage_percent} onLight
          label="Umumiy leksik qoplash"
          detail={`${report.token_count} tokendan ${report.matched_tokens} tasi mos. Ustma-ust mosliklar bir marta sanaladi.`} />
      </div>
      <div style={{ marginTop: "var(--sp-5)" }}><Alert variant="info" onLight>O‘xshashlik plagiatning avtomatik isboti emas.</Alert></div>
    </div>

    <div className={reportStyles.sheetBody}>
      <div className={reportStyles.workspace}>
        <aside className={reportStyles.sourceList}>
          <h3>Manbani tanlang</h3>
          <Stagger>
            {report.sources.map((item, index) => <StaggerItem key={item.id}>
              <button type="button" className={reportStyles.sourceButton} aria-pressed={sourceIndex === index}
                onClick={() => { setSourceIndex(index); setMatchIndex(0); }}>
                <span className={reportStyles.name}>{item.name}{item.corpus && <Badge variant="accent" onLight icon={<IconDatabase />}>Korpus</Badge>}</span>
                <span className={reportStyles.pct}>{percent(item.coverage_percent)}</span>
                <span className={reportStyles.count}>{item.matches.length} ta mos parcha</span>
              </button>
            </StaggerItem>)}
          </Stagger>
          <p className={reportStyles.meta}>Manba foizlari tekshirilgan hujjatga nisbatan; ular qo‘shilmaydi.</p>
        </aside>

        <div>
          {report.corpus?.included && <Alert variant="info" onLight>
            Ichki korpusdan {report.corpus.candidates_compared} ta nomzod solishtirildi ({report.corpus.candidate_limit} limiti). Limit tufayli korpusdagi barcha hujjatlar solishtirilmagan. Nomzodlar PostgreSQL full-text qidiruvi ({report.corpus.retrieval_policy}, <code>{report.corpus.fts_configuration}</code>) bilan tanlandi; bu o‘xshashlik ko‘rsatkichi emas.
            {report.corpus.normalization === "v3" && " O‘zbekcha qo‘shimchalarni hisobga oluvchi tajriba rejimi yoqilgan."}
          </Alert>}
          {!source?.matches.length && <Alert variant="warning" onLight>Ushbu manbada kamida 5 tokenli mos parcha topilmadi. Bu xulosa faqat yuklangan manbalar doirasida.</Alert>}

          {match && <div style={{ marginTop: report.corpus?.included || !source?.matches.length ? "var(--sp-5)" : 0 }}>
            <div className={reportStyles.matchControls}>
              <label htmlFor="match">Mos parchani tanlang</label>
              <Select id="match" onLight value={matchIndex} onChange={event => setMatchIndex(Number(event.target.value))} style={{ maxWidth: "20rem" }}>
                {source.matches.map((item, index) => <option key={index} value={index}>{index + 1}. {item.method === "exact" ? "Aynan mos" : "Normallashtirilgan shingle"} · {place(item.document.location)}</option>)}
              </Select>
            </div>
            <Crossfade id={`${sourceIndex}-${matchIndex}`}>
              <p className={pageStyles.muted} style={{ color: "var(--ink-on-light-muted)" }}>
                {match.method === "exact" ? "Original parcha belgima-belgi teng." : "Ketma-ket normalizatsiyalangan tokenlar teng; yozilish, apostrof, bo‘shliq yoki ko‘rinmas belgilar farq qilishi mumkin."}
              </p>
              {isDesktop
                ? <div className={reportStyles.excerptGrid} style={{ marginTop: "var(--sp-3)" }}>{documentPanel}{sourcePanel}</div>
                : <div style={{ marginTop: "var(--sp-3)" }}>
                    <Tabs onLight active={mobilePane} onChange={id => setMobilePane(id as "document" | "source")}
                      items={[{ id: "document", label: "Hujjat" }, { id: "source", label: "Manba" }]} />
                    <div style={{ marginTop: "var(--sp-3)" }}>{mobilePane === "document" ? documentPanel : sourcePanel}</div>
                  </div>}
            </Crossfade>
          </div>}

          <Disclosure className={reportStyles.limitations} defaultOpen summaryClassName={reportStyles.disclosureSummary} summary="Usul va cheklovlar">
            <p>5 tokenli shingle, kamida 5 tokenli ketma-ket moslik. Unicode NFKC, registr, apostrof variantlari va lotin harflari orasidagi U+200B/U+00AD/U+200C/U+FEFF ketma-ketligi normallashtiriladi. Siyosat: {report.parameters.normalization_version}. Algoritm: {report.parameters.algorithm_version}.</p>
            <ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul>
          </Disclosure>
        </div>
      </div>
    </div>
  </section>;
}
