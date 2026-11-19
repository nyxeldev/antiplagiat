-- Document-level reader visibility. "excerpt" (default) is today's only
-- behaviour unchanged: a report reader may see the matched passage plus
-- bounded context for a corpus source. "metadata_only" means the author has
-- restricted text display: the document still participates in retrieval and
-- its coverage still counts toward the percentage, but backend/corpus.py's
-- redact() never returns any excerpt or matched passage for it, only the
-- source's own metadata (title/author/year/coverage/match count).
--
-- The runtime role is never granted UPDATE on this column (see
-- backend/manage.py's migrate() grant list, unchanged by this migration), so
-- once set at ingest it is immutable through the application, the same way
-- permission_basis and uploaded_by_user_id already are through the existing
-- guard_corpus_document() trigger.
ALTER TABLE antiplagiat.corpus_documents
    ADD COLUMN visibility text NOT NULL DEFAULT 'excerpt'
        CHECK (visibility IN ('excerpt', 'metadata_only'));
