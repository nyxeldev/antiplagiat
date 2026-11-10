-- FAZA 2: teacher submission + moderation queue.
--
-- review_status gates search participation independently of the existing
-- storage lifecycle (status, migration 002): a submission is fully stored
-- (status='active') the moment it is uploaded, but stays out of retrieval
-- until a corpus_manager/admin approves it. backend/corpus.py's candidates()
-- picks this up with one added "AND review_status='approved'" clause --
-- backend/comparison/matching.py (the matching algorithm itself) is
-- untouched, and every document inserted before this migration defaults to
-- 'approved', so existing behaviour for admin/corpus_manager uploads is
-- unchanged.
--
-- Rejecting a submission reuses the existing withdraw mechanics (status ->
-- 'withdrawn', extracted_text purged, chunks blanked) instead of inventing a
-- second text-purge path, so the migration 002 immutability trigger and its
-- status/withdrawn_at/extracted_text CHECK invariant need no change: a
-- rejected document simply becomes withdrawn, with review_status='rejected'
-- and rejection_reason recording why.
ALTER TABLE antiplagiat.corpus_documents
    ADD COLUMN review_status text NOT NULL DEFAULT 'approved'
        CHECK (review_status IN ('pending', 'approved', 'rejected')),
    ADD COLUMN rejection_reason text,
    ADD CONSTRAINT corpus_documents_rejection_reason
        CHECK ((review_status = 'rejected' AND btrim(rejection_reason) <> '') OR
               (review_status <> 'rejected' AND rejection_reason IS NULL));
