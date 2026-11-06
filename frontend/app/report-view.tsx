"use client";
import { useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Crossfade, Disclosure, Pop, Stagger, StaggerItem } from "./motion";
import { useMediaQuery } from "./use-media-query";
import { Alert, Badge, IconButton } from "./ui/primitives";
import { Tabs } from "./ui/Tabs";
import { IconChevronRight, IconDatabase, IconX } from "./icons";
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

/** N distinct hues so a reader can tell sources apart in the document view and
 * the sources table -- assigned by position only, never by how much a source
 * matched, so color never reads as a risk level. */
const SOURCE_PALETTE = [1, 2, 3, 4, 5, 6].map(n => ({ solid: `var(--src-${n})`, soft: `var(--src-soft-${n})` }));
function sourceColor(index: number) { return SOURCE_PALETTE[index % SOURCE_PALETTE.length]; }

type FlatSpan = { sourceIndex: number; matchIndex: number; span: Span };

function CorpusExcerpt({ source, span }: { source: Source; span: Span }) {
  // The corpus text itself is never sent; only this bounded excerpt is.
  const meta = source.corpus!;
  const details = [meta.author_display, meta.doc_type, meta.year ? String(meta.year) : null].filter(Boolean).join(" · ");
  return <article className={reportStyles.excerpt}>
    <div className={reportStyles.excerptHead}><h4>{meta.title} <Badge variant="accent" onLight icon={<IconDatabase />}>Ichki korpus</Badge></h4></div>
    <div className={reportStyles.excerptBody}>
      <p className={pageStyles.muted}>{details || "Metama’lumot ko‘rsatilmagan"}{meta.source_note ? ` · ${meta.source_note}` : ""}</p>
      <p className={pageStyles.muted}>{place(span.location)}</p>
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
      <p className={pageStyles.muted}>{place(span.location)}</p>
      <p className={reportStyles.text}>{span.start > 120 && "…"}{points.slice(Math.max(0, span.start - 120), span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end, span.end + 120).join("")}{span.end + 120 < points.length && "…"}</p>
      <Disclosure summary="To‘liq ajratilgan matn" summaryClassName={reportStyles.disclosureSummary}>
        <p className={reportStyles.text} style={{ marginTop: "var(--sp-3)" }}>{points.slice(0, span.start).join("")}<mark>{points.slice(span.start, span.end).join("")}</mark>{points.slice(span.end).join("")}</p>
      </Disclosure>
    </div>
  </article>;
}

/** The checked document in full, with every matched span marked inline in its
 * source's color. Offsets come straight from the report -- nothing here
 * recomputes a match or a position. */
function DocumentReading({ text, spans, activeIndex, onPick }: { text: string; spans: FlatSpan[]; activeIndex: number; onPick: (index: number) => void }) {
  const points = useMemo(() => Array.from(text), [text]);
  const nodes = useMemo(() => {
    const out: ReactNode[] = [];
    let cursor = 0;
    spans.forEach((item, idx) => {
      if (item.span.start > cursor) out.push(<span key={`t${idx}`}>{points.slice(cursor, item.span.start).join("")}</span>);
      const color = sourceColor(item.sourceIndex);
      const style = { "--src-color": color.solid, "--src-soft": color.soft } as CSSProperties;
      out.push(
        <mark key={idx} data-span-index={idx} tabIndex={0} role="button" style={style}
          className={idx === activeIndex ? `${reportStyles.docMark} ${reportStyles.docMarkActive}` : reportStyles.docMark}
          aria-label={`${idx + 1}-mos joy`} onClick={() => onPick(idx)}
          onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(idx); } }}>
          {points.slice(item.span.start, item.span.end).join("")}
        </mark>,
      );
      cursor = item.span.end;
    });
    if (cursor < points.length) out.push(<span key="tail">{points.slice(cursor).join("")}</span>);
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, spans, activeIndex]);
  return <div className={reportStyles.docText}>{nodes}</div>;
}

export default function ReportView({ report }: { report: Report }) {
  const [selectedSource, setSelectedSource] = useState<number | null>(null);
  const [activeMatch, setActiveMatch] = useState<{ sourceIndex: number; matchIndex: number } | null>(null);
  const [activeSpan, setActiveSpan] = useState(-1);
  const [mobilePane, setMobilePane] = useState<"document" | "source">("document");
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const docRef = useRef<HTMLDivElement>(null);

  const totalMatches = report.sources.reduce((sum, s) => sum + s.matches.length, 0);
  const matchedSources = report.sources
    .map((source, index) => ({ source, index }))
    .filter(({ source }) => source.matches.length > 0);
  const remaining = Math.max(0, 100 - report.coverage_percent);

  const visibleSpans = useMemo<FlatSpan[]>(() => {
    const picks: FlatSpan[] = selectedSource === null
      ? report.sources.flatMap((s, si) => s.matches.map((m, mi) => ({ sourceIndex: si, matchIndex: mi, span: m.document })))
      : report.sources[selectedSource].matches.map((m, mi) => ({ sourceIndex: selectedSource, matchIndex: mi, span: m.document }));
    picks.sort((a, b) => a.span.start - b.span.start);
    const out: FlatSpan[] = [];
    for (const item of picks) {
      const prev = out[out.length - 1];
      if (prev && item.span.start < prev.span.end) continue; // overlap across sources: keep the earliest-starting one
      out.push(item);
    }
    return out;
  }, [report.sources, selectedSource]);

  function selectSource(index: number) {
    setSelectedSource(current => (current === index ? null : index));
    setActiveSpan(-1); setActiveMatch(null);
  }

  function goTo(nextIndex: number) {
    if (!visibleSpans.length) return;
    const wrapped = ((nextIndex % visibleSpans.length) + visibleSpans.length) % visibleSpans.length;
    const item = visibleSpans[wrapped];
    setActiveSpan(wrapped);
    setActiveMatch({ sourceIndex: item.sourceIndex, matchIndex: item.matchIndex });
    docRef.current?.querySelector(`[data-span-index="${wrapped}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  function closePanel() { setActiveMatch(null); }

  const activeSource = activeMatch ? report.sources[activeMatch.sourceIndex] : null;
  const activeMatchData = activeSource && activeMatch ? activeSource.matches[activeMatch.matchIndex] : null;
  const sourcePanel = activeMatchData && activeSource && (activeSource.corpus
    ? <CorpusExcerpt source={activeSource} span={activeMatchData.source} />
    : <Excerpt document={activeSource} span={activeMatchData.source} />);
  const documentPanel = activeMatchData && <Excerpt document={report.document} span={activeMatchData.document} />;

  return <section className={reportStyles.sheet} aria-labelledby="result-title" data-surface="light">
    <div className={reportStyles.sheetHead}>
      <div className={pageStyles.sectionHeading} style={{ marginBottom: 0 }}>
        <h2 id="result-title" style={{ color: "var(--ink-on-light)" }}>Solishtirish hisoboti</h2>
        <Badge variant="neutral" onLight>{report.sources.length} ta manba</Badge>
      </div>
      <p className={reportStyles.meta}>Saqlangan: {new Date(report.created_at).toLocaleString("uz-UZ")}</p>

      <div className={reportStyles.headlineNumbers}>
        <div className={reportStyles.headlineStat}>
          <span className={reportStyles.headlineValue} style={{ color: "var(--accent-ink-on-soft)" }}>{percent(report.coverage_percent)}</span>
          <span className={reportStyles.headlineLabel}>Ko‘chirilgan</span>
        </div>
        <div className={reportStyles.headlineStat}>
          <span className={reportStyles.headlineValue} style={{ color: "var(--ink-on-light-muted)" }}>{percent(remaining)}</span>
          <span className={reportStyles.headlineLabel}>Qolgan qism</span>
        </div>
      </div>
      <p className={reportStyles.headlineNote}>Faqat tekshirilgan {report.sources.length} ta manba bo‘yicha. Boshqa manbalar tekshirilmagan.</p>
      <p className={reportStyles.headlineSentence}>
        Hujjatning {percent(report.coverage_percent)} i tekshirilgan manbalarda topildi. {totalMatches} ta joyda, {matchedSources.length} ta hujjatdan.
      </p>

      <div style={{ marginTop: "var(--sp-5)" }}>
        <Alert variant="info" onLight>
          Tizim so‘zlarning ustma-ust tushishini o‘lchaydi. To‘g‘ri rasmiylashtirilgan iqtibos ham hisobga kiradi.
          Boshqa so‘zlar bilan qayta yozilgan matn topilmaydi. Yakuniy qarorni mutaxassis qabul qiladi.
        </Alert>
      </div>
    </div>

    <div className={reportStyles.sheetBody}>
      <h3 className={reportStyles.sectionTitle}>Ko‘chirilgan hujjatlar</h3>
      {matchedSources.length
        ? <>
            <div className={reportStyles.sourcesTable}>
              <div className={reportStyles.sourcesHeaderRow}><span>Hujjat</span><span>Muallif / yil</span><span>Foiz</span><span>Mos joy</span></div>
              <Stagger>
                {matchedSources.map(({ source, index }) => {
                  const meta = source.corpus;
                  const authorYear = meta ? [meta.author_display, meta.year ?? null].filter(Boolean).join(" · ") || "—" : "—";
                  return <StaggerItem key={source.id}>
                    <div role="button" tabIndex={0} aria-pressed={selectedSource === index} className={reportStyles.sourcesRow}
                      onClick={() => selectSource(index)}
                      onKeyDown={event => {
                        if (event.target !== event.currentTarget) return;
                        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectSource(index); }
                      }}>
                      <span className={reportStyles.sourceName}>
                        <span className={reportStyles.sourceDot} style={{ background: sourceColor(index).solid }} aria-hidden="true" />
                        {source.name}{source.corpus && <Badge variant="accent" onLight icon={<IconDatabase />}>Korpus</Badge>}
                      </span>
                      <span>{authorYear}</span>
                      <span className={reportStyles.sourcePct}>{percent(source.coverage_percent)}</span>
                      <span>{source.matches.length}</span>
                    </div>
                  </StaggerItem>;
                })}
              </Stagger>
            </div>
            {selectedSource !== null && <button type="button" className={reportStyles.resetFilter} onClick={() => selectSource(selectedSource)}>Barcha manbalarni ko‘rsatish</button>}
          </>
        : <Alert variant="info" onLight>Tekshirilgan manbalarning birortasida kamida 5 tokenli mos parcha topilmadi.</Alert>}

      <div className={reportStyles.docSection}>
        <div className={reportStyles.docNav}>
          <h3 className={reportStyles.sectionTitle} style={{ margin: 0 }}>
            Tekshirilgan hujjat <Badge variant="neutral" onLight>{visibleSpans.length} ta joy topildi</Badge>
          </h3>
          <div className={reportStyles.docNavButtons}>
            <IconButton label="Oldingi moslik" onLight icon={<IconChevronRight style={{ transform: "rotate(180deg)" }} />}
              disabled={!visibleSpans.length} onClick={() => goTo(activeSpan - 1)} />
            <span className={reportStyles.docNavCount}>{activeSpan >= 0 ? `${activeSpan + 1} / ${visibleSpans.length}` : `— / ${visibleSpans.length}`}</span>
            <IconButton label="Keyingi moslik" onLight icon={<IconChevronRight />}
              disabled={!visibleSpans.length} onClick={() => goTo(activeSpan + 1)} />
          </div>
        </div>
        <div ref={docRef}>
          <DocumentReading text={report.document.text ?? ""} spans={visibleSpans} activeIndex={activeSpan} onPick={goTo} />
        </div>
      </div>

      <Pop show={!!activeMatchData}>
        {activeMatchData && activeMatch && <div className={reportStyles.pairedPanel}>
          <div className={reportStyles.pairedPanelHead}>
            <h4>{activeSpan + 1}-moslik tafsiloti</h4>
            <IconButton label="Yopish" onLight icon={<IconX />} onClick={closePanel} />
          </div>
          <Crossfade id={`${activeMatch.sourceIndex}-${activeMatch.matchIndex}`}>
            <p className={pageStyles.muted} style={{ color: "var(--ink-on-light-muted)" }}>
              {activeMatchData.method === "exact" ? "Original parcha belgima-belgi teng." : "Ketma-ket normalizatsiyalangan tokenlar teng; yozilish, apostrof, bo‘shliq yoki ko‘rinmas belgilar farq qilishi mumkin."}
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
      </Pop>

      <Disclosure className={reportStyles.limitations} summaryClassName={reportStyles.disclosureSummary} summary="Texnik ma’lumot">
        {report.corpus?.included && <p>
          Ichki korpusdan {report.corpus.candidates_compared} ta nomzod solishtirildi ({report.corpus.candidate_limit} limiti).
          Limit tufayli korpusdagi barcha hujjatlar solishtirilmagan — bu to‘liq qamrov emas.
          Nomzodlar PostgreSQL full-text qidiruvi ({report.corpus.retrieval_policy}, <code>{report.corpus.fts_configuration}</code>) bilan tanlandi; bu o‘xshashlik ko‘rsatkichi emas.
          {report.corpus.normalization === "v3" && " O‘zbekcha qo‘shimchalarni hisobga oluvchi tajriba rejimi yoqilgan."}
        </p>}
        <p>5 tokenli shingle, kamida 5 tokenli ketma-ket moslik. Unicode NFKC, registr, apostrof variantlari va lotin harflari orasidagi U+200B/U+00AD/U+200C/U+FEFF ketma-ketligi normallashtiriladi. Siyosat: {report.parameters.normalization_version}. Algoritm: {report.parameters.algorithm_version}.</p>
        <ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul>
        {totalMatches > 0 && <>
          <p style={{ marginTop: "var(--sp-4)" }}>Har bir moslikning aniq joylashuvi (belgilar oralig‘i, hujjat bo‘yicha):</p>
          <div className={reportStyles.offsetTable}>
            <div className={reportStyles.offsetHeaderRow}><span>Manba</span><span>Joylashuv</span><span>Belgilar</span><span>Usul</span></div>
            {report.sources.flatMap((source, si) => source.matches.map((m, mi) => (
              <div className={reportStyles.offsetRow} key={`${si}-${mi}`}>
                <span>{source.name}</span>
                <span>{place(m.document.location)}</span>
                <span>[{m.document.start}, {m.document.end})</span>
                <span>{m.method === "exact" ? "Aynan mos" : "Shingle"}</span>
              </div>
            )))}
          </div>
        </>}
      </Disclosure>
    </div>
  </section>;
}
