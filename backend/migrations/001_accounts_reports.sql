CREATE TABLE antiplagiat.users (
    id uuid PRIMARY KEY,
    username text UNIQUE NOT NULL CHECK (username ~ '^[a-z0-9][a-z0-9_.-]{2,63}$'),
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'reviewer', 'corpus_manager', 'admin')),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE antiplagiat.sessions (
    token_hash char(64) PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES antiplagiat.users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX sessions_expiry ON antiplagiat.sessions(expires_at);
CREATE TABLE antiplagiat.reports (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES antiplagiat.users(id),
    request_key uuid NOT NULL,
    input_digest char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    algorithm_version text NOT NULL,
    normalization_version text NOT NULL,
    snapshot jsonb,
    deleted_at timestamptz,
    UNIQUE (owner_id, request_key),
    CHECK ((deleted_at IS NULL AND snapshot IS NOT NULL) OR
           (deleted_at IS NOT NULL AND snapshot IS NULL))
);
CREATE INDEX reports_owner_history ON antiplagiat.reports(owner_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;
-- Runtime may only purge snapshot text once. No editing of saved evidence.
CREATE FUNCTION antiplagiat.guard_report() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.request_key IS DISTINCT FROM OLD.request_key OR NEW.input_digest IS DISTINCT FROM OLD.input_digest
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.algorithm_version IS DISTINCT FROM OLD.algorithm_version
       OR NEW.normalization_version IS DISTINCT FROM OLD.normalization_version
       OR OLD.deleted_at IS NOT NULL OR NEW.deleted_at IS NULL OR NEW.snapshot IS NOT NULL THEN
        RAISE EXCEPTION 'Report snapshots are immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_report BEFORE UPDATE ON antiplagiat.reports
    FOR EACH ROW EXECUTE FUNCTION antiplagiat.guard_report();
