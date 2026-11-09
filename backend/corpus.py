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
# Per-user x per-document cumulative cap on MATCH TEXT (not context) shown
# across SEPARATE reports -- closes docs/decisions.md Sect.2's "unlimited
# aggregation" gap. Shape: a fraction of the document's own size, clamped
# between a floor and a ceiling (see redact()'s docstring for the reasoning
# behind each number).
CORPUS_DOCUMENT_BUDGET_FRACTION = 0.15
CORPUS_DOCUMENT_BUDGET_FLOOR = CORPUS_MATCH_CHARS
CORPUS_DOCUMENT_BUDGET_CEILING = 6_000
BUDGET_EXHAUSTED_REASON = (
    "Bu korpus hujjati bo‘yicha sizga ko‘rsatish byudjeti tugadi: moslik va foiz "
    "hamon ko‘rinadi, lekin matn parchasi endi berilmaydi. Byudjet avvalgi "
    "hisobotni qayta ochishda sarflanmaydi -- faqat yangi tekshiruv yaratilganda."
)
DOC_TYPES = ("bmi", "dissertatsiya", "kurs_ishi", "maqola", "boshqa")
# "excerpt" (default): a reader may see the matched passage plus bounded
# context for this corpus source, as redact() already does today.
# "metadata_only": the author has restricted text display. The document still
# participates in retrieval and its coverage still counts toward the overall
# percentage (compare() never looks at visibility), but redact() withholds
# every excerpt and matched passage for it -- only metadata (title, author,
# year, coverage percent, match count) ever reaches a reader.
VISIBILITIES = ("excerpt", "metadata_only")
RESTRICTED_REASON = "Muallif matn ko‘rsatilishini cheklagan."
# "approved" (default): participates in retrieval, same as every document
# added before this existed. "pending": a teacher's submission, fully stored
# but excluded from candidates() until a corpus_manager/admin reviews it --
# see migration 005. "rejected": reviewed and declined; reject() also moves
# status to "withdrawn" and purges the text, reusing withdraw()'s mechanics
# rather than a second purge path.
REVIEW_STATUSES = ("pending", "approved", "rejected")
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


def query_windows(tokens, normalization="v2", text=None):
    """Evenly sampled windows of the checked document, as plain query phrases.

    normalization="v3" runs each phrase through the uz-latin-v3 stripper so
    the query side matches what was indexed into fts_v3. It needs `text`
    (the original string `tokens` was produced from) to build each window
    from the ORIGINAL casing at those offsets, not `t["value"]" -- that
    value is already casefolded by matching.tokenize(), and stemming a
    casefolded word is not the same operation as stemming the original one:
    uz_latin_v3's proper-noun guard reads the leading letter's case, so
    stemming the casefolded value would silently skip that guard on every
    query (see docs/benchmarks/uz-morph-v3.md, C2, for the bug this fixes
    and the measured mismatch it caused between what got indexed and what a
    verbatim query for the same text produced).
    """
    if len(tokens) <= QUERY_WINDOW_TOKENS:
        windows = [tokens]
    else:
        starts = sorted({round(i * (len(tokens) - QUERY_WINDOW_TOKENS) / (MAX_QUERY_WINDOWS - 1))
                         for i in range(MAX_QUERY_WINDOWS)})
        windows = [tokens[s:s + QUERY_WINDOW_TOKENS] for s in starts]
    if normalization == "v3":
        if text is None:
            raise ValueError("normalization='v3' requires the original text (for its casing)")
        return [stem_text(" ".join(text[t["start"]:t["end"]] for t in w)) for w in windows]
    return [" ".join(t["value"] for t in w) for w in windows]


def metadata_errors(metadata):
    problems = []
    if not str(metadata.get("title", "")).strip():
        problems.append("Sarlavha majburiy.")
    if not str(metadata.get("permission_basis", "")).strip():
        problems.append("Ruxsat asosi majburiy; usiz hujjat korpusga kirmaydi.")
    if metadata.get("doc_type") not in DOC_TYPES:
        problems.append("Hujjat turi noto‘g‘ri: " + "/".join(DOC_TYPES) + ".")
    if (metadata.get("visibility") or "excerpt") not in VISIBILITIES:
        problems.append("Ko‘rinish darajasi noto‘g‘ri: " + "/".join(VISIBILITIES) + ".")
    year = metadata.get("year")
    if year is not None and not (isinstance(year, int) and 1900 <= year <= 2300):
        problems.append("Yil 1900–2300 oralig‘ida bo‘lishi kerak.")
    for field, limit in (("title", 300), ("author_display", 300), ("source_note", 2000),
                         ("permission_basis", 2000), ("language_hint", 32), ("original_filename", 300)):
        if len(str(metadata.get(field, "") or "")) > limit:
            problems.append(f"{field} uzunligi {limit} belgidan oshmasligi kerak.")
    return problems


def add_document(metadata, extracted, uploaded_by, raw_bytes, config=None,
                 chunk_tokens=CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS, document_id=None,
                 review_status="approved"):
    """Store one already extracted document together with its retrieval chunks.

    document_id defaults to a fresh random uuid4, as before. The retrieval
    evaluation harness is the only caller that passes a fixed uuid5 (derived
    from the benchmark manifest's own document id), so that the ranking tie
    break on corpus_document_id in candidates() is reproducible across runs,
    not dependent on a freshly randomised id each time.

    review_status is never taken from metadata (client-supplied, multipart
    text fields): it is a keyword the calling endpoint sets itself, "approved"
    for the existing admin/corpus_manager upload path (unchanged default) and
    "pending" for a teacher's submission -- a client can never approve its
    own upload by sending a form field.
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
           len(extracted["text"]), len(tokens), Jsonb(extracted["segments"]),
           metadata.get("visibility") or "excerpt", review_status)
    with database(config) as conn:
        # Handled inside the transaction: database() turns any psycopg.Error into a
        # generic 503, so a duplicate must be classified before it escapes.
        try:
            conn.execute(
                "INSERT INTO antiplagiat.corpus_documents(id,title,author_display,doc_type,year,"
                "language_hint,source_note,permission_basis,uploaded_by_user_id,original_filename,"
                "content_sha256,extracted_text,extraction_policy,char_count,token_count,segments,"
                "visibility,review_status)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", row)
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
            "char_count": len(extracted["text"]), "review_status": review_status}


def list_documents(page=1, status="active", config=None, *, review_status=None, uploaded_by=None):
    """review_status and uploaded_by are additional, optional filters (None =
    unfiltered, backward compatible with every existing positional call).
    The moderation queue passes review_status="pending"; a teacher's own
    submissions view passes uploaded_by=<their id> so they never see another
    teacher's submissions.
    """
    # Validated here so a direct call behaves the same as one routed by FastAPI.
    if status not in ("active", "withdrawn", "all"):
        raise CorpusError("corpus_filter", "Holat filtri noto‘g‘ri.", 400)
    if review_status is not None and review_status not in REVIEW_STATUSES:
        raise CorpusError("corpus_filter", "Ko‘rib chiqish holati filtri noto‘g‘ri.", 400)
    try:
        page = min(max(int(page), 1), 100_000)
    except (TypeError, ValueError):
        page = 1
    offset = (page - 1) * PAGE_SIZE
    with database(config) as conn:
        rows = conn.execute(
            "SELECT id,title,author_display,doc_type,year,language_hint,source_note,permission_basis,"
            "original_filename,content_sha256,char_count,token_count,status,review_status,"
            "rejection_reason,uploaded_by_user_id,created_at,withdrawn_at"
            " FROM antiplagiat.corpus_documents WHERE (%s='all' OR status=%s)"
            " AND (%s::text IS NULL OR review_status=%s) AND (%s::uuid IS NULL OR uploaded_by_user_id=%s)"
            " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (status, status, review_status, review_status, uploaded_by, uploaded_by,
             PAGE_SIZE + 1, offset)).fetchall()
    return {"page": page, "has_next": len(rows) > PAGE_SIZE,
            "items": [{**r, "id": str(r["id"]), "uploaded_by_user_id": str(r["uploaded_by_user_id"]),
                       "created_at": r["created_at"].isoformat(),
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


def get_document(document_id, config=None):
    """Full record for one document, any status/review_status -- for a
    moderator to actually read before approving or rejecting it, and for a
    teacher to check their own submission. Never exposed to a plain reader:
    gated the same way as the rest of this module's write-side functions,
    by the caller (corpus_api.py's role checks).
    """
    try:
        document_id = str(uuid.UUID(str(document_id)))
    except (ValueError, TypeError, AttributeError):
        raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "SELECT id,title,author_display,doc_type,year,language_hint,source_note,permission_basis,"
            "visibility,original_filename,content_sha256,extracted_text,char_count,token_count,"
            "status,review_status,rejection_reason,uploaded_by_user_id,created_at,withdrawn_at"
            " FROM antiplagiat.corpus_documents WHERE id=%s", (document_id,)).fetchone()
    if not row:
        raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi.", 404)
    return {**row, "id": str(row["id"]), "uploaded_by_user_id": str(row["uploaded_by_user_id"]),
            "created_at": row["created_at"].isoformat(),
            "withdrawn_at": row["withdrawn_at"].isoformat() if row["withdrawn_at"] else None}


def approve(document_id, config=None):
    """Admit a teacher's pending submission into retrieval. Does not touch
    status/extracted_text: the document was already fully stored, just
    excluded from candidates() by review_status -- approving only flips
    that one gate.
    """
    try:
        document_id = str(uuid.UUID(str(document_id)))
    except (ValueError, TypeError, AttributeError):
        raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "UPDATE antiplagiat.corpus_documents SET review_status='approved'"
            " WHERE id=%s AND status='active' AND review_status='pending' RETURNING id,title",
            (document_id,)).fetchone()
    if not row:
        raise CorpusError("corpus_not_found",
                          "Korpus hujjati topilmadi yoki allaqachon ko‘rib chiqilgan.", 404)
    return {"id": str(row["id"]), "title": row["title"], "review_status": "approved"}


def reject(document_id, reason, config=None):
    """Decline a teacher's pending submission. A reason is mandatory and
    recorded; the text is purged the same way withdraw() purges it (reusing
    its exact mechanics -- status becomes "withdrawn" too, so the migration
    002 CHECK invariant and immutability trigger need no change), so no
    rejected document's text survives anywhere.
    """
    if not str(reason or "").strip():
        raise CorpusError("corpus_metadata", "Rad etish sababi majburiy.", 400)
    try:
        document_id = str(uuid.UUID(str(document_id)))
    except (ValueError, TypeError, AttributeError):
        raise CorpusError("corpus_not_found", "Korpus hujjati topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "UPDATE antiplagiat.corpus_documents SET status='withdrawn',withdrawn_at=now(),"
            "updated_at=now(),extracted_text=NULL,review_status='rejected',rejection_reason=%s"
            " WHERE id=%s AND status='active' AND review_status='pending' RETURNING id,title",
            (str(reason).strip(), document_id)).fetchone()
        if not row:
            raise CorpusError("corpus_not_found",
                              "Korpus hujjati topilmadi yoki allaqachon ko‘rib chiqilgan.", 404)
        conn.execute("UPDATE antiplagiat.corpus_chunks SET chunk_text='',chunk_text_uz_latin_v3=''"
                     " WHERE corpus_document_id=%s", (document_id,))
    return {"id": str(row["id"]), "title": row["title"], "review_status": "rejected"}


def candidates(tokens, limit=DEFAULT_CANDIDATES, operator="OR", normalization="v2", text=None):
    """Ranked candidate corpus documents. The rank is a retrieval score only.

    operator defaults to "OR" (the running application's only behaviour,
    unchanged). The retrieval evaluation harness is the only caller that
    passes "AND", to A/B plainto_tsquery's native all-terms-required ranking
    against the OR rewrite used in production.

    normalization defaults to "v2" (the running application's only
    behaviour, unchanged): candidate chunks are matched through the
    uz-latin-v2 `fts` column, and `text` is not needed. "v3" is opt-in --
    today only scripts/eval_retrieval.py passes it -- and matches through
    `fts_v3` instead, built from the rule-based stripper in
    backend/comparison/uz_latin_v3.py; it requires `text` (the original
    string `tokens` came from) so query_windows() can recover each token's
    real casing, the same casing the indexed side already sees (see
    query_windows()'s docstring). Either way the match itself is decided
    later by the exact/shingle algorithm on the untouched original text,
    never by this rank.
    """
    if operator not in ("OR", "AND"):
        raise ValueError("operator must be 'OR' or 'AND'")
    if normalization not in NORMALIZATIONS:
        raise ValueError("normalization must be 'v2' or 'v3'")
    limit = max(1, min(int(limit), MAX_CANDIDATES))
    phrases = [p for p in query_windows(tokens, normalization, text) if p.strip()]
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
            "JOIN antiplagiat.corpus_documents d ON d.id = c.corpus_document_id "
            "AND d.status='active' AND d.review_status='approved' "
            "GROUP BY c.corpus_document_id "
            "ORDER BY total_rank DESC, matched_chunks DESC, c.corpus_document_id "
            "LIMIT %s", (phrases, limit)).fetchall()
    return [{"id": str(r["id"]), "retrieval_rank": float(r["total_rank"]),
             "matched_chunks": r["matched_chunks"]} for r in rows], limit


def load_for_comparison(document_id):
    """Shape a stored corpus document like an extracted upload for compare().

    Every id this is ever called with already came from candidates(), which
    already filters to status='active' AND review_status='approved' -- the
    same filter is repeated here as defense in depth, not because any caller
    is known to need it.
    """
    with database() as conn:
        row = conn.execute(
            "SELECT id,title,author_display,doc_type,year,source_note,original_filename,"
            "extracted_text,segments,token_count,char_count,visibility FROM antiplagiat.corpus_documents"
            " WHERE id=%s AND status='active' AND review_status='approved'", (document_id,)).fetchone()
    if not row or row["extracted_text"] is None:
        return None
    return {"name": row["title"], "format": "corpus", "text": row["extracted_text"],
            "segments": row["segments"],
            "corpus": {"id": str(row["id"]), "title": row["title"],
                       "author_display": row["author_display"], "doc_type": row["doc_type"],
                       "year": row["year"], "source_note": row["source_note"],
                       "original_filename": row["original_filename"],
                       "visibility": row["visibility"], "char_count": row["char_count"]}}


def per_document_budget(char_count):
    """Lifetime cap (across all reports) on MATCH TEXT characters a single
    user may be shown for one corpus document.

    Fraction (15%): generous enough that a genuine reviewer can confirm
    several distinct matches against the same source over multiple real
    sessions, while still keeping cumulative exposure to a small share of
    any document long enough for the fraction to matter (see the ceiling).

    Floor (CORPUS_MATCH_CHARS, 1200): without it, a short document's 15%
    could fall below one truncated match's own length, which would make the
    very first, totally fresh query withhold text for a document nobody has
    seen yet -- defeating the feature (redact() guarantees at least one full
    match is shown before any budget is ever spent). The floor also means a
    short document (under ~8000 characters, where 15% < the floor) is
    proportionally MORE exposed than a long one -- an accepted, documented
    residual limitation (docs/decisions.md Sect.2), not something this
    formula tries to close.

    Ceiling (6000 = 5x CORPUS_MATCH_CHARS): without it, a long document (a
    full dissertation can run to hundreds of thousands of characters) would
    let its 15% grow to tens of thousands of characters -- a real
    reconstruction risk, exactly what Sect.2 flagged as open. The ceiling
    caps the maximum ever assembled, from ANY document regardless of size,
    at about five matches' worth: enough to substantiate several distinct
    findings, not enough to rebuild a real paper.
    """
    return int(min(max(char_count * CORPUS_DOCUMENT_BUDGET_FRACTION, CORPUS_DOCUMENT_BUDGET_FLOOR),
                   CORPUS_DOCUMENT_BUDGET_CEILING))


def _already_shown_chars(user_id, document_ids, config=None):
    """Cumulative MATCH TEXT characters already shown to this user, per
    document, from backend/corpus.py's own audit log (migration 007) --
    never from the text itself, which this table does not store.
    """
    if not document_ids:
        return {}
    with database(config) as conn:
        rows = conn.execute(
            "SELECT corpus_document_id, SUM(chars_shown) AS spent FROM antiplagiat.corpus_excerpt_audit"
            " WHERE user_id=%s AND corpus_document_id = ANY(%s) GROUP BY corpus_document_id",
            (user_id, document_ids)).fetchall()
    return {str(r["corpus_document_id"]): r["spent"] for r in rows}


def record_excerpt_disclosures(user_id, report_id, debits, config=None):
    """One audit row per (user, corpus document) actually revealed in this
    report -- chars_shown only, never the excerpt text. Called once, AFTER
    reports.save() has given the report its id (redact() runs before that
    row exists, so it can only hand back what to debit, not write it itself).
    """
    if not debits:
        return
    with database(config) as conn:
        conn.cursor().executemany(
            "INSERT INTO antiplagiat.corpus_excerpt_audit(id,user_id,corpus_document_id,report_id,chars_shown)"
            " VALUES (%s,%s,%s,%s,%s)",
            [(uuid.uuid4(), user_id, document_id, report_id, chars) for document_id, chars in debits.items()])


def redact(result, user_id=None, config=None):
    """Replace full corpus text with bounded excerpts before the report is saved.

    The checked document keeps its own text; only corpus sources are reduced.
    The report-wide budget (CORPUS_EXCERPT_BUDGET) governs the surrounding
    CONTEXT, which is corpus text the reader has not otherwise seen, within
    this one report. It is unchanged by what follows.

    user_id=None (every existing caller/test that never passed one) keeps
    the exact old behaviour: no database access, no cross-report budget --
    this is deliberately preserved so backend/tests/test_corpus.py's pure,
    no-database redaction tests stay meaningful and unchanged. The real
    production caller (backend/comparison/api.py's with_corpus()) always has
    an authenticated user and passes it, which additionally enforces
    per_document_budget(): the cumulative MATCH TEXT (not context) shown to
    THAT user for THAT corpus document, across every separate report ever
    created -- not just this one. This is what actually closes
    docs/decisions.md Sect.2's gap: today's CORPUS_EXCERPT_BUDGET resets on
    every new /compare call, so nothing stopped many separate requests from
    together reassembling an unbounded share of a document; this one does
    not reset, because it is read from (and added to) the database rather
    than a fresh local variable.

    Matches are walked in order and each one is binary: shown in full (up to
    CORPUS_MATCH_CHARS) or not at all, never partially -- so the budget is
    always spent in whole-match units, and a document's budget floor
    (CORPUS_DOCUMENT_BUDGET_FLOOR == CORPUS_MATCH_CHARS) guarantees the
    FIRST match of the FIRST report against a fresh document always fits,
    however many more matches that same report finds. Once a document's
    budget for this user is spent, later matches for it keep their
    coverage_percent/location/source name -- compare()'s own coverage
    accounting (backend/comparison/matching.py) never looks at any of this
    -- only the text passage itself is withheld, with budget_exhausted_reason
    explaining why.

    Admin/corpus_manager get no special-cased exemption here: the budget
    applies to every role identically through this comparison path. They
    already have a separate, role-gated, unredacted path to the same text
    (corpus_api.py's GET /corpus/documents/{id}, for moderation) -- their
    corpus-management role does not need to ALSO make this reader-facing,
    budget-protected path unlimited.

    metadata_only sources never reach the loop below at all for the budget
    (see `restricted`): they give no excerpt in the first place, so nothing
    is ever spent for them.

    Reopening an already saved report never calls this function again
    (backend/reports.py's get() returns the stored, already-redacted
    snapshot) -- so the budget is only ever spent once, at creation.
    """
    budget = CORPUS_EXCERPT_BUDGET
    corpus_sources = [s for s in result.get("sources", []) if s.get("corpus")]
    budgetable_ids = [s["corpus"]["id"] for s in corpus_sources
                      if s["corpus"].get("visibility") != "metadata_only" and s["corpus"].get("char_count") is not None]
    spent = _already_shown_chars(user_id, budgetable_ids, config) if user_id is not None else {}
    debits = {}
    for source in corpus_sources:
        text = source.pop("text", "")
        source.pop("segments", None)
        source["text_withheld"] = True
        restricted = source["corpus"].get("visibility") == "metadata_only"
        if restricted:
            source["restricted"] = True
            source["restriction_reason"] = RESTRICTED_REASON
        document_id = source["corpus"]["id"]
        char_count = source["corpus"].get("char_count")
        remaining = None
        if not restricted and user_id is not None and char_count is not None:
            remaining = per_document_budget(char_count) - spent.get(document_id, 0)
        for match in source.get("matches", []):
            side = match["source"]
            if restricted:
                # No fragment of corpus text reaches the reader at all, not even
                # the matched passage itself -- only that a match exists and how
                # it counted toward coverage_percent (computed upstream in
                # matching.py, untouched here).
                side.pop("text", None)
                continue
            truncated = len(side["text"]) > CORPUS_MATCH_CHARS
            match_text = side["text"][:CORPUS_MATCH_CHARS] if truncated else side["text"]
            if remaining is not None and len(match_text) > remaining:
                side.pop("text", None)
                side["budget_exhausted"] = True
                side["budget_exhausted_reason"] = BUDGET_EXHAUSTED_REASON
                continue
            if remaining is not None:
                remaining -= len(match_text)
                debits[document_id] = debits.get(document_id, 0) + len(match_text)
            start, end = side["start"], side["end"]
            flat_room = max(0, min(CORPUS_CONTEXT_CHARS, budget // 2))
            # Independently cap each side by a fraction of what that side
            # actually has available outside the match.
            room_before = min(flat_room, int(start * CORPUS_CONTEXT_FRACTION))
            room_after = min(flat_room, int((len(text) - end) * CORPUS_CONTEXT_FRACTION))
            before = text[max(0, start - room_before):start]
            after = text[end:end + room_after]
            budget = max(0, budget - len(before) - len(after))
            side["text"] = match_text
            side["match_truncated"] = truncated
            side["excerpt"] = {"before": before, "after": after}
    result["excerpt_policy"] = {
        "context_chars": CORPUS_CONTEXT_CHARS, "match_chars": CORPUS_MATCH_CHARS,
        "report_context_budget_chars": CORPUS_EXCERPT_BUDGET,
        "document_budget_fraction": CORPUS_DOCUMENT_BUDGET_FRACTION,
        "document_budget_floor_chars": CORPUS_DOCUMENT_BUDGET_FLOOR,
        "document_budget_ceiling_chars": CORPUS_DOCUMENT_BUDGET_CEILING,
        "note": "Korpus manbasidan faqat mos parcha va cheklangan kontekst ko‘rsatiladi; "
                "to‘liq korpus matni berilmaydi. Har bir korpus hujjati bo‘yicha "
                "ko‘rsatilgan matn umumiy hajmi foydalanuvchi uchun cheklangan.",
    }
    if user_id is not None:
        result["_excerpt_debits"] = debits
    return result
