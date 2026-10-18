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
from backend.comparison.uz_latin_v3 import stem_text
from backend.persistence import ServiceError, database

RETRIEVAL_POLICY = "pg-fts-candidate-v1"
FTS_CONFIGURATION = "simple"
# "v2" (default, the running application's only behaviour) reads the
# uz-latin-v2 `fts` column built straight from chunk_text. "v3" is opt-in --
# today only scripts/eval_retrieval.py passes it -- and reads `fts_v3`,
# built from chunk_text run through the rule-based stripper in
# backend/comparison/uz_latin_v3.py. Neither touches extracted_text,
# segments or offsets; both are retrieval-only.
NORMALIZATIONS = ("v2", "v3")

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
# A flat per-side cap alone can expose nearly a whole short document: a 200-char
# window on each side of a short match can cover everything outside the match.
# This second cap limits context to a fraction of what is actually available on
# that side (outside the match), so some of a short document's text always
# stays hidden even when the flat cap alone would not have limited it.
CORPUS_CONTEXT_FRACTION = 0.5
DOC_TYPES = ("bmi", "dissertatsiya", "kurs_ishi", "maqola", "boshqa")
PAGE_SIZE = 20


class CorpusError(ServiceError):
    """Corpus specific failure that is already safe to show to a caller."""


def digest_text(data):
    return hashlib.sha256(data).hexdigest()


def chunk_document(text, tokens, chunk_tokens=CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS):
    """Fixed token windows mapped back to original character offsets.

    chunk_tokens/overlap_tokens default to the runtime constants, so every
    caller in the running application (HTTP ingest, CLI) is unaffected; the
    retrieval evaluation harness (scripts/eval_retrieval.py) is the only
    caller that passes other values, to A/B a different chunk window.
    """
    step = chunk_tokens - overlap_tokens
    chunks = []
    for index, start in enumerate(range(0, max(len(tokens) - overlap_tokens, 1), step)):
        window = tokens[start:start + chunk_tokens]
        if not window:
            break
        char_start, char_end = window[0]["start"], window[-1]["end"]
        chunks.append({"chunk_index": index, "char_start": char_start, "char_end": char_end,
                       "token_start": start, "token_end": start + len(window),
                       "chunk_text": text[char_start:char_end]})
        if start + chunk_tokens >= len(tokens):
            break
    return chunks


def query_windows(tokens, normalization="v2"):
    """Evenly sampled windows of the checked document, as plain query phrases.

    normalization="v3" runs each phrase through the uz-latin-v3 stripper so
    the query side matches what was indexed into fts_v3; it never changes
    `tokens` itself, only the throwaway phrase string built here.
    """
    if len(tokens) <= QUERY_WINDOW_TOKENS:
        phrases = [" ".join(t["value"] for t in tokens)]
    else:
        starts = sorted({round(i * (len(tokens) - QUERY_WINDOW_TOKENS) / (MAX_QUERY_WINDOWS - 1))
                         for i in range(MAX_QUERY_WINDOWS)})
        phrases = [" ".join(t["value"] for t in tokens[s:s + QUERY_WINDOW_TOKENS]) for s in starts]
    return [stem_text(p) for p in phrases] if normalization == "v3" else phrases


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


def add_document(metadata, extracted, uploaded_by, raw_bytes, config=None,
                 chunk_tokens=CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS, document_id=None):
    """Store one already extracted document together with its retrieval chunks.

    document_id defaults to a fresh random uuid4, as before. The retrieval
    evaluation harness is the only caller that passes a fixed uuid5 (derived
    from the benchmark manifest's own document id), so that the ranking tie
    break on corpus_document_id in candidates() is reproducible across runs,
    not dependent on a freshly randomised id each time.
    """
    problems = metadata_errors(metadata)
    if problems:
        raise CorpusError("corpus_metadata", " ".join(problems), 400)
    tokens = tokenize(extracted["text"])
    chunks = chunk_document(extracted["text"], tokens, chunk_tokens, overlap_tokens)
    if not chunks:
        raise CorpusError("corpus_empty", "Hujjatdan indekslanadigan matn olinmadi.", 422)
    document_id = document_id or uuid.uuid4()
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
                "char_end,token_start,token_end,chunk_text,chunk_text_uz_latin_v3)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(uuid.uuid4(), document_id, c["chunk_index"], c["char_start"], c["char_end"],
                  c["token_start"], c["token_end"], c["chunk_text"], stem_text(c["chunk_text"]))
                 for c in chunks])
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
        conn.execute("UPDATE antiplagiat.corpus_chunks SET chunk_text='',chunk_text_uz_latin_v3=''"
                     " WHERE corpus_document_id=%s", (document_id,))
    return {"id": str(row["id"]), "title": row["title"], "status": "withdrawn"}


def candidates(tokens, limit=DEFAULT_CANDIDATES, operator="OR", normalization="v2"):
    """Ranked candidate corpus documents. The rank is a retrieval score only.

    operator defaults to "OR" (the running application's only behaviour,
    unchanged). The retrieval evaluation harness is the only caller that
    passes "AND", to A/B plainto_tsquery's native all-terms-required ranking
    against the OR rewrite used in production.

    normalization defaults to "v2" (the running application's only
    behaviour, unchanged): candidate chunks are matched through the
    uz-latin-v2 `fts` column. "v3" is opt-in -- today only
    scripts/eval_retrieval.py passes it -- and matches through `fts_v3`
    instead, built from the rule-based stripper in
    backend/comparison/uz_latin_v3.py. Either way the match itself is
    decided later by the exact/shingle algorithm on the untouched original
    text, never by this rank.
    """
    if operator not in ("OR", "AND"):
        raise ValueError("operator must be 'OR' or 'AND'")
    if normalization not in NORMALIZATIONS:
        raise ValueError("normalization must be 'v2' or 'v3'")
    limit = max(1, min(int(limit), MAX_CANDIDATES))
    phrases = [p for p in query_windows(tokens, normalization) if p.strip()]
    if not phrases:
        return [], limit
    fts_column = "fts" if normalization == "v2" else "fts_v3"
    with database() as conn:
        conn.execute(f"SET LOCAL statement_timeout = {RETRIEVAL_TIMEOUT_MS}")
        # plainto_tsquery joins terms with AND, which would only match a chunk
        # containing the whole window verbatim. Rewriting the already parsed and
        # quoted tsquery to OR keeps the escaping while ranking by overlap, which
        # is what candidate selection needs. The match itself is decided later by
        # the exact/shingle algorithm, never by this rank.
        query_expr = ("plainto_tsquery('simple', phrase)" if operator == "AND" else
                      "replace(plainto_tsquery('simple', phrase)::text, ' & ', ' | ')::tsquery")
        rows = conn.execute(
            f"WITH q AS (SELECT {query_expr} AS query FROM unnest(%s::text[]) AS phrase) "
            "SELECT c.corpus_document_id AS id, "
            f"       sum(ts_rank(c.{fts_column}, q.query)) AS total_rank, "
            "       count(DISTINCT c.id) AS matched_chunks "
            f"FROM q JOIN antiplagiat.corpus_chunks c ON c.{fts_column} @@ q.query "
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
            flat_room = max(0, min(CORPUS_CONTEXT_CHARS, budget // 2))
            # Independently cap each side by a fraction of what that side
            # actually has available outside the match.
            room_before = min(flat_room, int(start * CORPUS_CONTEXT_FRACTION))
            room_after = min(flat_room, int((len(text) - end) * CORPUS_CONTEXT_FRACTION))
            before = text[max(0, start - room_before):start]
            after = text[end:end + room_after]
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
