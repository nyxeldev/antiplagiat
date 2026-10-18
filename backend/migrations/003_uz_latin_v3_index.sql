-- Opt-in uz-latin-v3 retrieval index, alongside the existing uz-latin-v2
-- `fts` column (unchanged). See backend/comparison/uz_latin_v3.py for the
-- rule-based suffix stripper that fills chunk_text_uz_latin_v3; it is always
-- computed from chunk_text in Python at ingest time, never derived inside
-- Postgres, so the stripping rules stay in one reviewable file.
--
-- chunk_text_uz_latin_v3 is retrieval-only: it is never the original text,
-- never exposed to a reader and never used to compute offsets. The real
-- `chunk_text` (and extracted_text/segments, used for highlighting) are
-- untouched by this migration.
--
-- Existing rows get '' until their document is re-ingested; v3 candidate
-- search simply will not find them through fts_v3 until then. v2 stays the
-- only retrieval path for the running application; v3 is read only by the
-- opt-in evaluation harness (scripts/eval_retrieval.py).
ALTER TABLE antiplagiat.corpus_chunks
    ADD COLUMN chunk_text_uz_latin_v3 text NOT NULL DEFAULT '';
ALTER TABLE antiplagiat.corpus_chunks
    ADD COLUMN fts_v3 tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', chunk_text_uz_latin_v3)) STORED;
CREATE INDEX corpus_chunks_fts_v3 ON antiplagiat.corpus_chunks USING GIN (fts_v3);
