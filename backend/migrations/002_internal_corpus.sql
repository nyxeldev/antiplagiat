-- Internal permission-based corpus. Documents are stored only with a recorded
-- permission basis; withdrawing one purges its text and takes it out of retrieval.
CREATE TABLE antiplagiat.corpus_documents (
    id uuid PRIMARY KEY,
    title text NOT NULL CHECK (btrim(title) <> '' AND length(title) <= 300),
    author_display text NOT NULL CHECK (length(author_display) <= 300),
    doc_type text NOT NULL CHECK (doc_type IN ('bmi', 'dissertatsiya', 'kurs_ishi', 'maqola', 'boshqa')),
    year integer CHECK (year IS NULL OR year BETWEEN 1900 AND 2300),
    language_hint text NOT NULL DEFAULT 'uz' CHECK (length(language_hint) <= 32),
    source_note text NOT NULL DEFAULT '' CHECK (length(source_note) <= 2000),
    -- Written evidence that the academy may store and compare this text.
    permission_basis text NOT NULL CHECK (btrim(permission_basis) <> '' AND length(permission_basis) <= 2000),
    uploaded_by_user_id uuid NOT NULL REFERENCES antiplagiat.users(id),
    original_filename text NOT NULL CHECK (length(original_filename) <= 300),
    content_sha256 char(64) NOT NULL,
    extracted_text text,
    extraction_policy text NOT NULL,
    char_count integer NOT NULL CHECK (char_count >= 0),
    token_count integer NOT NULL CHECK (token_count >= 0),
    segments jsonb NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    withdrawn_at timestamptz,
    CHECK ((status = 'active' AND withdrawn_at IS NULL AND extracted_text IS NOT NULL) OR
           (status = 'withdrawn' AND withdrawn_at IS NOT NULL AND extracted_text IS NULL))
);
-- The same file may be re-added only after the earlier copy was withdrawn.
CREATE UNIQUE INDEX corpus_documents_active_digest
    ON antiplagiat.corpus_documents(content_sha256) WHERE status = 'active';
CREATE INDEX corpus_documents_listing
    ON antiplagiat.corpus_documents(created_at DESC, id DESC);

CREATE TABLE antiplagiat.corpus_chunks (
    id uuid PRIMARY KEY,
    corpus_document_id uuid NOT NULL REFERENCES antiplagiat.corpus_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    -- Offsets into corpus_documents.extracted_text, Unicode code points, end-exclusive.
    char_start integer NOT NULL CHECK (char_start >= 0),
    char_end integer NOT NULL CHECK (char_end > char_start),
    token_start integer NOT NULL CHECK (token_start >= 0),
    token_end integer NOT NULL CHECK (token_end > token_start),
    chunk_text text NOT NULL,
    -- 'simple' on purpose: PostgreSQL ships no Uzbek dictionary and the English
    -- stemmer mangles Uzbek word forms. See docs/architecture.md.
    fts tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED,
    UNIQUE (corpus_document_id, chunk_index)
);
CREATE INDEX corpus_chunks_fts ON antiplagiat.corpus_chunks USING GIN (fts);

-- Retrieval only ever reads chunks of active documents.
CREATE INDEX corpus_chunks_document ON antiplagiat.corpus_chunks(corpus_document_id);

-- Corpus rows are evidence: the runtime role may add, withdraw and purge, never
-- rewrite identity, permission basis or provenance.
CREATE FUNCTION antiplagiat.guard_corpus_document() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
       OR NEW.permission_basis IS DISTINCT FROM OLD.permission_basis
       OR NEW.uploaded_by_user_id IS DISTINCT FROM OLD.uploaded_by_user_id
       OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.extraction_policy IS DISTINCT FROM OLD.extraction_policy THEN
        RAISE EXCEPTION 'Corpus provenance is immutable';
    END IF;
    IF OLD.status = 'withdrawn' THEN
        RAISE EXCEPTION 'Withdrawn corpus documents are final';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_corpus_document BEFORE UPDATE ON antiplagiat.corpus_documents
    FOR EACH ROW EXECUTE FUNCTION antiplagiat.guard_corpus_document();
