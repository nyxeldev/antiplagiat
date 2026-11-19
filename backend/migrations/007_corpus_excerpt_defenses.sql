-- FAZA 3: closes docs/decisions.md Sect.2's "unlimited aggregation" gap with
-- two independent defenses, plus the audit log that makes the first one
-- auditable.
--
-- (1) corpus_excerpt_audit: records how much excerpt TEXT a user has been
-- shown for a given corpus document, so backend/corpus.py's redact() can
-- enforce a cumulative per-user x per-document budget across SEPARATE
-- /compare requests (today's budget, CORPUS_EXCERPT_BUDGET, only ever
-- bounded ONE report). The text itself is deliberately never a column here
-- -- only sizes and identifiers -- so this table cannot become a second
-- copy of corpus content. Append-only: the runtime role gets SELECT+INSERT,
-- never UPDATE/DELETE (see backend/manage.py's migrate()).
--
-- (2) rate_limit_counters: a per-user, per-scope fixed-window request
-- counter for the comparison and corpus endpoints, persisted here (not in
-- process memory) specifically so a backend restart does not reset it.
CREATE TABLE antiplagiat.corpus_excerpt_audit (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES antiplagiat.users(id),
    corpus_document_id uuid NOT NULL REFERENCES antiplagiat.corpus_documents(id),
    report_id uuid NOT NULL REFERENCES antiplagiat.reports(id),
    chars_shown integer NOT NULL CHECK (chars_shown > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
-- The budget check's own read pattern: "how much has this user already seen
-- of this document, in total".
CREATE INDEX corpus_excerpt_audit_budget
    ON antiplagiat.corpus_excerpt_audit(user_id, corpus_document_id);
-- For the retention cleanup docs/decisions.md Sect.2 proposes (not yet
-- implemented as a scheduled job -- see that entry).
CREATE INDEX corpus_excerpt_audit_retention
    ON antiplagiat.corpus_excerpt_audit(created_at);

CREATE TABLE antiplagiat.rate_limit_counters (
    user_id uuid NOT NULL REFERENCES antiplagiat.users(id) ON DELETE CASCADE,
    scope text NOT NULL,
    window_start timestamptz NOT NULL,
    count integer NOT NULL DEFAULT 0 CHECK (count > 0),
    PRIMARY KEY (user_id, scope, window_start)
);
