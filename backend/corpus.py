"""Internal permission-based corpus: storage, PostgreSQL FTS candidate retrieval
and the redaction that keeps full corpus text out of non-admin responses.

Parsing never happens here. Uploaded files are extracted by the sandboxed worker
(backend/comparison/worker.py); this module only stores and reads already
extracted text, so the parser keeps its own resource limits and the database
credentials stay out of the worker process.
"""
import hashlib
import uuid

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from backend.comparison.matching import NORMALIZATION_VERSION, tokenize
from backend.persistence import ServiceError, database

RETRIEVAL_POLICY = "pg-fts-candidate-v1"
FTS_CONFIGURATION = "simple"

# A ~40 token window with ~20 token overlap keeps every five-token shingle whole
# inside at least one chunk, so a borrowed sentence cannot fall between chunks.
CHUNK_TOKENS = 40
CHUNK_OVERLAP_TOKENS = 20
# Query windows are built the same way but sampled, so a long document costs a
# bounded number of tsquery evaluations.
QUERY_WINDOW_TOKENS = 40
MAX_QUERY_WINDOWS = 12
DEFAULT_CANDIDATES = 5
MAX_CANDIDATES = 10
RETRIEVAL_TIMEOUT_MS = 5000
# Non-admin readers only ever see the matched run plus bounded context.
CORPUS_CONTEXT_CHARS = 200
CORPUS_MATCH_CHARS = 1200
CORPUS_EXCERPT_BUDGET = 20_000
DOC_TYPES = ("bmi", "dissertatsiya", "kurs_ishi", "maqola", "boshqa")
PAGE_SIZE = 20


class CorpusError(ServiceError):
    """Corpus specific failure that is already safe to show to a caller."""


def digest_text(data):
    return hashlib.sha256(data).hexdigest()


def chunk_document(text, tokens):
    """Fixed token windows mapped back to original character offsets."""
    step = CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
    chunks = []
    for index, start in enumerate(range(0, max(len(tokens) - CHUNK_OVERLAP_TOKENS, 1), step)):
        window = tokens[start:start + CHUNK_TOKENS]
        if not window:
            break
        char_start, char_end = window[0]["start"], window[-1]["end"]
        chunks.append({"chunk_index": index, "char_start": char_start, "char_end": char_end,
                       "token_start": start, "token_end": start + len(window),
                       "chunk_text": text[char_start:char_end]})
        if start + CHUNK_TOKENS >= len(tokens):
            break
    return chunks


def query_windows(tokens):
    """Evenly sampled windows of the checked document, as plain query phrases."""
    if len(tokens) <= QUERY_WINDOW_TOKENS:
        return [" ".join(t["value"] for t in tokens)]
    starts = sorted({round(i * (len(tokens) - QUERY_WINDOW_TOKENS) / (MAX_QUERY_WINDOWS - 1))
                     for i in range(MAX_QUERY_WINDOWS)})
    return [" ".join(t["value"] for t in tokens[s:s + QUERY_WINDOW_TOKENS]) for s in starts]


def metadata_errors(metadata):
    problems = []
    if not str(metadata.get("title", "")).strip():
        problems.append("Sarlavha majburiy.")
    if not str(metadata.get("permission_basis", "")).strip():
        problems.append("Ruxsat asosi majburiy; usiz hujjat korpusga kirmaydi.")
    if metadata.get("doc_type") not in DOC_TYPES:
        problems.append("Hujjat turi noto‘g‘ri: " + "/".join(DOC_TYPES) + ".")
    year = metadata.get("year")
    if year is not None and not (isinstance(year, int) and 1900 <= year <= 2300):
        problems.append("Yil 1900–2300 oralig‘ida bo‘lishi kerak.")
    for field, limit in (("title", 300), ("author_display", 300), ("source_note", 2000),
                         ("permission_basis", 2000), ("language_hint", 32), ("original_filename", 300)):
        if len(str(metadata.get(field, "") or "")) > limit:
            problems.append(f"{field} uzunligi {limit} belgidan oshmasligi kerak.")
    return problems


def add_document(metadata, extracted, uploaded_by, raw_bytes, config=None):
    """Store one already extracted document together with its retrieval chunks."""
    problems = metadata_errors(metadata)
    if problems:
        raise CorpusError("corpus_metadata", " ".join(problems), 400)
    tokens = tokenize(extracted["text"])
    chunks = chunk_document(extracted["text"], tokens)
    if not chunks:
        raise CorpusError("corpus_empty", "Hujjatdan indekslanadigan matn olinmadi.", 422)
    document_id = uuid.uuid4()
    row = (document_id, str(metadata["title"]).strip(), str(metadata.get("author_display", "") or ""),
           metadata["doc_type"], metadata.get("year"), str(metadata.get("language_hint") or "uz"),
           str(metadata.get("source_note", "") or ""), str(metadata["permission_basis"]).strip(),
           uploaded_by, str(metadata.get("original_filename", "") or extracted.get("name", "")),
           digest_text(raw_bytes), extracted["text"], NORMALIZATION_VERSION,
           len(extracted["text"]), len(tokens), Jsonb(extracted["segments"]))
    with database(config) as conn:
        # Handled inside the transaction: database() turns any psycopg.Error into a
        # generic 503, so a duplicate must be classified before it escapes.
        try:
            conn.execute(
                "INSERT INTO antiplagiat.corpus_documents(id,title,author_display,doc_type,year,"
                "language_hint,source_note,permission_basis,uploaded_by_user_id,original_filename,"
                "content_sha256,extracted_text,extraction_policy,char_count,token_count,segments)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", row)
            conn.cursor().executemany(
                "INSERT INTO antiplagiat.corpus_chunks(id,corpus_document_id,chunk_index,char_start,"
                "char_end,token_start,token_end,chunk_text) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(uuid.uuid4(), document_id, c["chunk_index"], c["char_start"], c["char_end"],
                  c["token_start"], c["token_end"], c["chunk_text"]) for c in chunks])
        except UniqueViolation as error:
            if error.diag.constraint_name == "corpus_documents_active_digest":
                raise CorpusError("corpus_duplicate", "Bu fayl korpusda allaqachon mavjud.", 409) from None
            raise
    return {"id": str(document_id), "chunk_count": len(chunks), "token_count": len(tokens),
            "char_count": len(extracted["text"])}


def list_documents(page=1, status="active", config=None):
    # Validated here so a direct call behaves the same as one routed by FastAPI.
    if status not in ("active", "withdrawn", "all"):
        raise CorpusError("corpus_filter", "Holat filtri noto‘g‘ri.", 400)
    try:
        page = min(max(int(page), 1), 100_000)
    except (TypeError, ValueError):
        page = 1
    offset = (page - 1) * PAGE_SIZE
    with database(config) as conn:
        rows = conn.execute(
            "SELECT id,title,author_display,doc_type,year,language_hint,source_note,permission_basis,"
            "original_filename,content_sha256,char_count,token_count,status,created_at,withdrawn_at"
            " FROM antiplagiat.corpus_documents WHERE (%s='all' OR status=%s)"
            " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (status, status, PAGE_SIZE + 1, offset)).fetchall()
    return {"page": page, "has_next": len(rows) > PAGE_SIZE,
            "items": [{**r, "id": str(r["id"]), "created_at": r["created_at"].isoformat(),
                       "withdrawn_at": r["withdrawn_at"].isoformat() if r["withdrawn_at"] else None}
                      for r in rows[:PAGE_SIZE]]}


def withdraw(document_id, config=None):
    """Take a document out of retrieval and purge its stored text."""
    try:
        document_id = str(uuid.UUID(str(document_id)))
    except (ValueError, TypeError, AttributeError):
        raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "UPDATE antiplagiat.corpus_documents SET status='withdrawn',withdrawn_at=now(),"
            "updated_at=now(),extracted_text=NULL WHERE id=%s AND status='active' RETURNING id,title",
            (document_id,)).fetchone()
        if not row:
            raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi yoki allaqachon chiqarilgan.", 404)
        conn.execute("UPDATE antiplagiat.corpus_chunks SET chunk_text='' WHERE corpus_document_id=%s",
                     (document_id,))
    return {"id": str(row["id"]), "title": row["title"], "status": "withdrawn"}


def candidates(tokens, limit=DEFAULT_CANDIDATES):
    """Ranked candidate corpus documents. The rank is a retrieval score only."""
    limit = max(1, min(int(limit), MAX_CANDIDATES))
    phrases = [p for p in query_windows(tokens) if p.strip()]
    if not phrases:
        return [], limit
    with database() as conn:
        conn.execute(f"SET LOCAL statement_timeout = {RETRIEVAL_TIMEOUT_MS}")
        # plainto_tsquery joins terms with AND, which would only match a chunk
        # containing the whole window verbatim. Rewriting the already parsed and
        # quoted tsquery to OR keeps the escaping while ranking by overlap, which
        # is what candidate selection needs. The match itself is decided later by
        # the exact/shingle algorithm, never by this rank.
        rows = conn.execute(
            "WITH q AS (SELECT replace(plainto_tsquery('simple', phrase)::text, ' & ', ' | ')::tsquery AS query "
            "           FROM unnest(%s::text[]) AS phrase) "
            "SELECT c.corpus_document_id AS id, "
            "       sum(ts_rank(c.fts, q.query)) AS total_rank, "
            "       count(DISTINCT c.id) AS matched_chunks "
            "FROM q JOIN antiplagiat.corpus_chunks c ON c.fts @@ q.query "
            "JOIN antiplagiat.corpus_documents d ON d.id = c.corpus_document_id AND d.status='active' "
            "GROUP BY c.corpus_document_id "
            "ORDER BY total_rank DESC, matched_chunks DESC, c.corpus_document_id "
            "LIMIT %s", (phrases, limit)).fetchall()
    return [{"id": str(r["id"]), "retrieval_rank": float(r["total_rank"]),
             "matched_chunks": r["matched_chunks"]} for r in rows], limit


def load_for_comparison(document_id):
    """Shape a stored corpus document like an extracted upload for compare()."""
    with database() as conn:
        row = conn.execute(
            "SELECT id,title,author_display,doc_type,year,source_note,original_filename,"
            "extracted_text,segments,token_count FROM antiplagiat.corpus_documents"
            " WHERE id=%s AND status='active'", (document_id,)).fetchone()
    if not row or row["extracted_text"] is None:
        return None
    return {"name": row["title"], "format": "corpus", "text": row["extracted_text"],
            "segments": row["segments"],
            "corpus": {"id": str(row["id"]), "title": row["title"],
                       "author_display": row["author_display"], "doc_type": row["doc_type"],
                       "year": row["year"], "source_note": row["source_note"],
                       "original_filename": row["original_filename"]}}


def redact(result):
    """Replace full corpus text with bounded excerpts before the report is saved.

    The checked document keeps its own text; only corpus sources are reduced.
    The report-wide budget governs the surrounding context, which is corpus text
    the reader has not otherwise seen. The matched run itself is capped
    separately: it is by definition identical to text already in the checked
    document, so counting it against the budget would hide evidence without
    protecting anything.
    """
    budget = CORPUS_EXCERPT_BUDGET
    for source in result.get("sources", []):
        if not source.get("corpus"):
            continue
        text = source.pop("text", "")
        source.pop("segments", None)
        source["text_withheld"] = True
        for match in source.get("matches", []):
            side = match["source"]
            start, end = side["start"], side["end"]
            truncated = len(side["text"]) > CORPUS_MATCH_CHARS
            room = max(0, min(CORPUS_CONTEXT_CHARS, budget // 2))
            before = text[max(0, start - room):start]
            after = text[end:end + room]
            budget = max(0, budget - len(before) - len(after))
            side["text"] = side["text"][:CORPUS_MATCH_CHARS] if truncated else side["text"]
            side["match_truncated"] = truncated
            side["excerpt"] = {"before": before, "after": after}
    result["excerpt_policy"] = {
        "context_chars": CORPUS_CONTEXT_CHARS, "match_chars": CORPUS_MATCH_CHARS,
        "report_context_budget_chars": CORPUS_EXCERPT_BUDGET,
        "note": "Korpus manbasidan faqat mos parcha va cheklangan kontekst ko‘rsatiladi; "
                "to‘liq korpus matni berilmaydi.",
    }
    return result
