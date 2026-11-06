"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/client-api";
import { useSessionExpired, useUser } from "../account-shell";
import { IconDatabase, IconPlus, IconTrash } from "../icons";
import { Pop, Rise } from "../motion";
import { Alert, Badge, Button, Card, EmptyState, Field, IconButton, Input, Pagination, Select, Skeleton } from "../ui/primitives";
import { ConfirmDialog, Dialog } from "../ui/Dialog";
import { Dropzone } from "../ui/Dropzone";
import { FileItem } from "../ui/FileItem";
import styles from "./corpus.module.css";
import pageStyles from "../page.module.css";

const DOC_TYPE_LABEL: Record<string, string> = {
  bmi: "BMI", dissertatsiya: "Dissertatsiya", kurs_ishi: "Kurs ishi", maqola: "Maqola", boshqa: "Boshqa",
};
const STATUS_LABEL: Record<string, string> = { active: "Faol", withdrawn: "Chiqarilgan" };
const MIB = 1024 * 1024;

type Item = {
  id: string; title: string; author_display: string; doc_type: string; year: number | null;
  language_hint: string; source_note: string; permission_basis: string; original_filename: string;
  content_sha256: string; char_count: number; token_count: number; status: string;
  created_at: string; withdrawn_at: string | null;
};

function fileError(file: File) {
  if (!/\.(txt|docx|pdf)$/i.test(file.name)) return "Faqat TXT, DOCX yoki PDF tanlang.";
  if (!file.size) return "Bo‘sh faylni qo‘shib bo‘lmaydi.";
  if (file.size > 10 * MIB) return "Fayl hajmi 10 MiB dan oshmasin.";
  return null;
}

export default function CorpusAdmin() {
  const user = useUser();
  const expired = useSessionExpired();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("active");
  const [version, setVersion] = useState(0);
  const [data, setData] = useState<{ items: Item[]; has_next: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<Item | null>(null);
  const [confirming, setConfirming] = useState<Item | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const allowed = !!user && (user.role === "admin" || user.role === "corpus_manager");

  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    api(`/corpus/documents?page=${page}&status=${status}`, { signal: controller.signal })
      .then(result => { setData(result); setError(null); })
      .catch(e => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Korpus ro‘yxati olinmadi.");
      });
    return () => controller.abort();
  }, [allowed, page, status, version, expired]);

  async function withdraw(item: Item) {
    setWithdrawing(true); setError(null);
    try {
      await api(`/corpus/documents/${item.id}/withdraw`, { method: "POST" });
      setConfirming(null); setDetail(null); setData(null); setVersion(v => v + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired(); else setError(e instanceof Error ? e.message : "Chiqarib bo‘lmadi.");
    } finally { setWithdrawing(false); }
  }

  if (!user) return null;
  if (!allowed) {
    return <Rise><Card>
      <EmptyState icon={<IconDatabase />} title="Ruxsat yo‘q"
        description="Bu bo‘lim faqat administrator yoki korpus boshqaruvchisi uchun." />
    </Card></Rise>;
  }

  return <Rise>
    <Card>
      <div className={pageStyles.sectionHeading}>
        <h2>Korpus boshqaruvi</h2>
        <Button icon={<IconPlus />} onClick={() => setAddOpen(true)}>Hujjat qo‘shish</Button>
      </div>
      <p className={pageStyles.muted}>Tekshiruvda nomzod manba sifatida ishlatiladigan hujjatlar. Matnning o‘zi hech qachon ko‘rsatilmaydi — faqat metama’lumot.</p>

      <div className={styles.filters}>
        <Select className={styles.select} value={status} aria-label="Holat bo‘yicha filtr"
          onChange={e => { setData(null); setStatus(e.target.value); setPage(1); }}>
          <option value="active">Faol</option>
          <option value="withdrawn">Chiqarilgan</option>
          <option value="all">Barchasi</option>
        </Select>
      </div>

      {error && <Alert variant="error">{error} <button onClick={() => { setData(null); setVersion(v => v + 1); }}
        style={{ background: "none", border: 0, color: "inherit", textDecoration: "underline", cursor: "pointer", font: "inherit" }}>Qayta urinish</button></Alert>}

      {!data && !error && <div className={styles.table} role="status" aria-label="Korpus yuklanmoqda">
        {[0, 1, 2].map(i => <Skeleton key={i} height="4.25rem" style={{ borderRadius: "var(--r-md)" }} />)}
      </div>}

      {data && <>
        {!data.items.length
          ? <EmptyState icon={<IconDatabase />} title="Hujjat yo‘q"
              description="Bu filtr bo‘yicha korpusda hujjat topilmadi." />
          : <div className={styles.table}>
              <div className={styles.headerRow}><span>Hujjat</span><span>Turi</span><span>Yil</span><span>Holat</span><span /></div>
              {data.items.map(item => (
                <div key={item.id} role="button" tabIndex={0} className={styles.row} onClick={() => setDetail(item)}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setDetail(item); } }}>
                  <div>
                    <div className={styles.title}>{item.title}</div>
                    <div className={styles.author}>{item.author_display}</div>
                  </div>
                  <span>{DOC_TYPE_LABEL[item.doc_type] ?? item.doc_type}</span>
                  <span className={styles.year}>{item.year ?? "—"}</span>
                  <Badge variant={item.status === "active" ? "accent" : "neutral"}>{STATUS_LABEL[item.status] ?? item.status}</Badge>
                  <span className={styles.actions} onClick={e => e.stopPropagation()}>
                    {item.status === "active" && (
                      <IconButton label={`“${item.title}”ni chiqarish`} icon={<IconTrash />} onClick={() => setConfirming(item)} />
                    )}
                  </span>
                </div>
              ))}
            </div>}
        {data.items.length > 0 && <Pagination page={page} hasNext={data.has_next} onChange={next => { setData(null); setPage(next); }} />}
      </>}
    </Card>

    <AddDocumentDialog open={addOpen} onClose={() => setAddOpen(false)}
      onAdded={() => { setAddOpen(false); setData(null); setVersion(v => v + 1); }} />

    <Dialog open={!!detail} onClose={() => setDetail(null)} title={detail?.title ?? ""}>
      {detail && <>
        <dl className={styles.detailGrid}>
          <dt>Muallif</dt><dd>{detail.author_display}</dd>
          <dt>Turi</dt><dd>{DOC_TYPE_LABEL[detail.doc_type] ?? detail.doc_type}</dd>
          <dt>Yil</dt><dd>{detail.year ?? "—"}</dd>
          <dt>Til</dt><dd>{detail.language_hint}</dd>
          <dt>Manba izohi</dt><dd>{detail.source_note || "—"}</dd>
          <dt>Ruxsat asosi</dt><dd>{detail.permission_basis}</dd>
          <dt>Asl fayl nomi</dt><dd>{detail.original_filename}</dd>
          <dt>Hajmi</dt><dd>{detail.char_count.toLocaleString("uz-UZ")} belgi, {detail.token_count.toLocaleString("uz-UZ")} token</dd>
          <dt>Qo‘shilgan</dt><dd>{new Date(detail.created_at).toLocaleString("uz-UZ")}</dd>
          <dt>Holat</dt><dd><Badge variant={detail.status === "active" ? "accent" : "neutral"}>{STATUS_LABEL[detail.status] ?? detail.status}</Badge></dd>
        </dl>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--sp-3)" }}>
          <Button variant="secondary" onClick={() => setDetail(null)}>Yopish</Button>
          {detail.status === "active" && <Button variant="destructive" onClick={() => setConfirming(detail)}>Korpusdan chiqarish</Button>}
        </div>
      </>}
    </Dialog>

    <ConfirmDialog open={!!confirming} onClose={() => setConfirming(null)} onConfirm={() => confirming && withdraw(confirming)}
      title="Korpusdan chiqarish" confirmLabel="Chiqarish" busy={withdrawing}
      description={confirming && <>“{confirming.title}” korpusdan chiqariladi va uning matni butunlay o‘chiriladi. Bu amalni qaytarib bo‘lmaydi.</>} />
  </Rise>;
}

function AddDocumentDialog({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const expired = useSessionExpired();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [docType, setDocType] = useState("bmi");
  const [year, setYear] = useState("");
  const [language, setLanguage] = useState("uz");
  const [sourceNote, setSourceNote] = useState("");
  const [permissionBasis, setPermissionBasis] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  function reset() {
    setFile(null); setTitle(""); setAuthor(""); setDocType("bmi"); setYear("");
    setLanguage("uz"); setSourceNote(""); setPermissionBasis(""); setError(null);
  }
  function close() { if (busy) return; reset(); onClose(); }

  function pick(files: File[]) {
    const picked = files[0]; if (!picked) return;
    const problem = fileError(picked); if (problem) { setError(problem); return; }
    setError(null); setFile(picked);
    if (!title) setTitle(picked.name.replace(/\.(txt|docx|pdf)$/i, ""));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !title.trim() || !author.trim() || !permissionBasis.trim() || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    const data = new FormData();
    data.append("file", file); data.append("title", title); data.append("author_display", author);
    data.append("doc_type", docType); data.append("language_hint", language);
    data.append("source_note", sourceNote); data.append("permission_basis", permissionBasis);
    if (year) data.append("year", year);
    try {
      await api("/corpus/documents", { method: "POST", body: data, signal: AbortSignal.timeout(60_000) });
      reset(); onAdded();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setError(e instanceof Error && e.name !== "TimeoutError" ? e.message : "Vaqt tugadi. Qayta urinib ko‘ring.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <Dialog open={open} onClose={close} title="Korpusga hujjat qo‘shish">
    <form onSubmit={submit} className={styles.formGrid}>
      {!file
        ? <Dropzone label="Fayl tanlang yoki shu yerga tashlang" hint="UTF-8 TXT, DOCX yoki matn qatlamli PDF, 10 MiB gacha."
            accept=".txt,.docx,.pdf" onFiles={pick} onLight />
        : <FileItem name={file.name} size={file.size} onRemove={() => setFile(null)} removeLabel="Faylni olib tashlash" onLight />}

      <Field label="Sarlavha" htmlFor="corpus-title" onLight>
        <Input id="corpus-title" required maxLength={300} value={title} disabled={busy} onLight
          onChange={e => setTitle(e.target.value)} />
      </Field>
      <Field label="Muallif (ko‘rsatiladigan nom)" htmlFor="corpus-author" onLight>
        <Input id="corpus-author" required maxLength={300} value={author} disabled={busy} onLight
          onChange={e => setAuthor(e.target.value)} />
      </Field>
      <Field label="Turi" htmlFor="corpus-type" onLight>
        <Select id="corpus-type" value={docType} disabled={busy} onLight onChange={e => setDocType(e.target.value)}>
          {Object.entries(DOC_TYPE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </Select>
      </Field>
      <Field label="Yil (ixtiyoriy)" htmlFor="corpus-year" onLight>
        <Input id="corpus-year" type="number" min={1900} max={2300} value={year} disabled={busy} onLight
          onChange={e => setYear(e.target.value)} />
      </Field>
      <Field label="Til belgisi" htmlFor="corpus-lang" onLight>
        <Input id="corpus-lang" maxLength={32} value={language} disabled={busy} onLight
          onChange={e => setLanguage(e.target.value)} />
      </Field>
      <Field label="Manba izohi (ixtiyoriy)" htmlFor="corpus-note" onLight>
        <Input id="corpus-note" maxLength={2000} value={sourceNote} disabled={busy} onLight
          onChange={e => setSourceNote(e.target.value)} />
      </Field>
      <Field label="Ruxsat asosi (majburiy)" htmlFor="corpus-permission"
        hint="Bu hujjatni korpusga qo‘shish huquqi qayerdan kelganini qisqacha yozing." onLight>
        <Input id="corpus-permission" required maxLength={2000} value={permissionBasis} disabled={busy} onLight
          onChange={e => setPermissionBasis(e.target.value)} />
      </Field>

      <Pop show={!!error}>{error && <Alert variant="error" onLight>{error}</Alert>}</Pop>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--sp-3)" }}>
        <Button type="button" variant="secondary" onClick={close} disabled={busy}>Bekor qilish</Button>
        <Button type="submit" loading={busy} disabled={!file || !title.trim() || !author.trim() || !permissionBasis.trim()}>Qo‘shish</Button>
      </div>
    </form>
  </Dialog>;
}
