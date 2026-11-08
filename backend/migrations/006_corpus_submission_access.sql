-- Submitting to the corpus moderation queue (FAZA 2's /corpus/submissions) is
-- no longer every "user"-role account's right by default: an admin must grant
-- it per account. This is deliberately NOT a new database role (see
-- docs/decisions.md §12) -- a boolean flag on the existing account instead,
-- so migration 001's users.role CHECK constraint (checksummed, never touched
-- since) stays exactly as it is.
--
-- admin/corpus_manager are unaffected either way: backend/auth.py's
-- require_teacher() lets them through unconditionally, the same as before
-- this migration, since they already have their own unmoderated upload path.
ALTER TABLE antiplagiat.users
    ADD COLUMN can_submit_to_corpus boolean NOT NULL DEFAULT false;
