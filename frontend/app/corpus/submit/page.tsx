"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../../lib/client-api";
import { useSessionExpired, useUser } from "../../account-shell";
import { IconUpload } from "../../icons";
import { Pop, Rise } from "../../motion";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Pagination, Select, Skeleton } from "../../ui/primitives";
import { Dropzone } from "../../ui/Dropzone";
import { FileItem } from "../../ui/FileItem";
import corpusStyles from "../corpus.module.css";
import pageStyles from "../../page.module.css";
import styles from "./submit.module.css";

const DOC_TYPE_LABEL: Record<string, string> = {
  bmi: "BMI", dissertatsiya: "Dissertatsiya", kurs_ishi: "Kurs ishi", maqola: "Maqola", boshqa: "Boshqa",
};
const VISIBILITY_LABEL: Record<string, string> = { excerpt: "Parcha ko‘rinadi", metadata_only: "Faqat ma’lumot (matn yashirin)" };
const REVIEW_STATUS_LABEL: Record<string, string> = { pending: "Kutilmoqda", approved: "Tasdiqlangan", rejected: "Rad etilgan" };
const MIB = 1024 * 1024;

type Submission = {
  id: string; title: string; doc_type: string; status: string;
  review_status: string; rejection_reason: string | null; created_at: string;
};

function fileError(file: File) {
  if (!/\.(txt|docx|pdf)$/i.test(file.name)) return "Faqat TXT, DOCX yoki PDF tanlang.";
  if (!file.size) return "Bo‘sh faylni qo‘shib bo‘lmaydi.";
  if (file.size > 10 * MIB) return "Fayl hajmi 10 MiB dan oshmasin.";
  return null;
}

export default function SubmitCorpusDocument() {
  const user = useUser();
  const expired = useSessionExpired();
  // Defense in depth: the nav entry is already hidden from a flagless "user"
  // (see shell/AppShell.tsx), but a direct visit to this URL must refuse the
  // same way, not just not be linked to.
  const allowed = !!user && user.role === "user" && !!user.can_submit_to_corpus;

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("bmi");
  const [permissionBasis, setPermissionBasis] = useState("");
  const [visibility, setVisibility] = useState("excerpt");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const [page, setPage] = useState(1);
  const [version, setVersion] = useState(0);
  const [data, setData] = useState<{ items: Submission[]; has_next: boolean } | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    api(`/corpus/submissions?page=${page}`, { signal: controller.signal })
      .then(result => { setData(result); setListError(null); })
      .catch(e => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 401) expired();
        else setListError(e instanceof Error ? e.message : "Takliflar ro‘yxati olinmadi.");
      });
    return () => controller.abort();
  }, [allowed, page, version, expired]);

  function pick(files: File[]) {
    const picked = files[0]; if (!picked) return;
    const problem = fileError(picked); if (problem) { setFormError(problem); return; }
    setFormError(null); setFile(picked);
    if (!title) setTitle(picked.name.replace(/\.(txt|docx|pdf)$/i, ""));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !title.trim() || !permissionBasis.trim() || inFlight.current) return;
    inFlight.current = true; setBusy(true); setFormError(null);
    const body = new FormData();
    body.append("file", file); body.append("title", title); body.append("doc_type", docType);
    body.append("permission_basis", permissionBasis); body.append("visibility", visibility);
    try {
      await api("/corpus/submissions", { method: "POST", body, signal: AbortSignal.timeout(60_000) });
      setFile(null); setTitle(""); setDocType("bmi"); setPermissionBasis(""); setVisibility("excerpt");
      setData(null); setVersion(v => v + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired();
      else setFormError(e instanceof Error && e.name !== "TimeoutError" ? e.message : "Vaqt tugadi. Qayta urinib ko‘ring.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  if (!user) return null;
  if (!allowed) {
    return <Rise><Card>
      <EmptyState icon={<IconUpload />} title="Ruxsat yo‘q"
        description="Korpusga hujjat taklif qilish huquqini administrator berishi kerak." />
    </Card></Rise>;
  }

  return <Rise>
    <Card>
      <div className={pageStyles.sectionHeading}><h2>Korpusga hujjat taklif qilish</h2></div>
      <p className={pageStyles.muted}>Taklif qilingan hujjat administrator yoki korpus boshqaruvchisi tasdiqlagandan keyingina solishtirishda ishlatiladi. Rad etilsa, hujjat matni butunlay o‘chiriladi.</p>
      <form onSubmit={submit} className={corpusStyles.formGrid}>
        {!file
          ? <Dropzone label="Fayl tanlang yoki shu yerga tashlang" hint="UTF-8 TXT, DOCX yoki matn qatlamli PDF, 10 MiB gacha."
              accept=".txt,.docx,.pdf" onFiles={pick} />
          : <FileItem name={file.name} size={file.size} onRemove={() => setFile(null)} removeLabel="Faylni olib tashlash" />}
        <Field label="Sarlavha" htmlFor="submit-title">
          <Input id="submit-title" required maxLength={300} value={title} disabled={busy}
            onChange={e => setTitle(e.target.value)} />
        </Field>
        <Field label="Turi" htmlFor="submit-type">
          <Select id="submit-type" value={docType} disabled={busy} onChange={e => setDocType(e.target.value)}>
            {Object.entries(DOC_TYPE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </Field>
        <Field label="Ruxsat asosi (majburiy)" htmlFor="submit-permission"
          hint="Bu hujjatni korpusga taklif qilish huquqi qayerdan kelganini qisqacha yozing.">
          <Input id="submit-permission" required maxLength={2000} value={permissionBasis} disabled={busy}
            onChange={e => setPermissionBasis(e.target.value)} />
        </Field>
        <Field label="Ko‘rinish darajasi" htmlFor="submit-visibility"
          hint="Faqat ma’lumot: moslik va foiz hisoblanadi, lekin hech qanday matn parchasi ko‘rsatilmaydi.">
          <Select id="submit-visibility" value={visibility} disabled={busy} onChange={e => setVisibility(e.target.value)}>
            {Object.entries(VISIBILITY_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </Field>
        <Pop show={!!formError}>{formError && <Alert variant="error">{formError}</Alert>}</Pop>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button type="submit" loading={busy} disabled={!file || !title.trim() || !permissionBasis.trim()}>Taklif qilish</Button>
        </div>
      </form>
    </Card>

    <Card>
      <div className={pageStyles.sectionHeading}><h2>Mening takliflarim</h2></div>
      {listError && <Alert variant="error">{listError}</Alert>}
      {!data && !listError && <div className={styles.list} role="status" aria-label="Takliflar yuklanmoqda">
        {[0, 1].map(i => <Skeleton key={i} height="4.25rem" style={{ borderRadius: "var(--r-md)" }} />)}
      </div>}
      {data && (!data.items.length
        ? <EmptyState icon={<IconUpload />} title="Taklif yo‘q" description="Siz hali korpusga hujjat taklif qilmagansiz." />
        : <div className={styles.list}>
            {data.items.map(item => (
              <div key={item.id} className={styles.item}>
                <div className={styles.itemMain}>
                  <div className={styles.itemTitle}>{item.title}</div>
                  <div className={styles.itemMeta}>
                    {DOC_TYPE_LABEL[item.doc_type] ?? item.doc_type} · {new Date(item.created_at).toLocaleString("uz-UZ")}
                  </div>
                  {item.review_status === "rejected" && item.rejection_reason && (
                    <Alert variant="warning" compact>{item.rejection_reason}</Alert>
                  )}
                </div>
                <Badge variant={item.review_status === "rejected" ? "danger" : item.review_status === "pending" ? "cyan" : "accent"}>
                  {REVIEW_STATUS_LABEL[item.review_status] ?? item.review_status}
                </Badge>
              </div>
            ))}
          </div>)}
      {data && data.items.length > 0 && <Pagination page={page} hasNext={data.has_next} onChange={next => { setData(null); setPage(next); }} />}
    </Card>
  </Rise>;
}
