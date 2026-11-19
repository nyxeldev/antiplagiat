"""Per-user request-rate limiting, persisted in the database (migration 007)
so a count survives a backend restart -- an in-memory counter would not.

Fixed one-minute windows, not a sliding window: simple, auditable, and exact
enough for this purpose (see docs/decisions.md Sect.2 for why an approximate
boundary is an accepted trade-off here).
"""
from backend.persistence import ServiceError, database

WINDOW_SECONDS = 60
# "compare": POST /compare with include_corpus=true -- the only path that can
# expose any corpus excerpt, so it is the one this limit is really defending
# (a plain two-upload comparison touches no corpus text and is already
# serialized by comparison/api.py's own single-flight `gate` lock).
# "corpus": every backend/corpus_api.py endpoint -- lighter operations
# (listing, submitting, moderating), legitimately polled somewhat more often.
LIMITS = {"compare": 30, "corpus": 60}
MESSAGE = "Juda ko‘p so‘rov yuborildi. Bir necha soniyadan so‘ng qayta urinib ko‘ring."


def enforce(user_id, scope, config=None):
    """Raise ServiceError(429) once `scope`'s per-minute limit is exceeded
    for this user. Call AFTER the caller's own role/auth check, so a request
    that was going to be refused anyway never consumes a legitimate user's
    quota and an unauthenticated caller (no user_id yet) is never charged.
    """
    limit = LIMITS[scope]
    with database(config) as conn:
        row = conn.execute(
            "INSERT INTO antiplagiat.rate_limit_counters(user_id, scope, window_start, count)"
            " VALUES (%s, %s, date_trunc('minute', now()), 1)"
            " ON CONFLICT (user_id, scope, window_start) DO UPDATE"
            " SET count = antiplagiat.rate_limit_counters.count + 1"
            " RETURNING count", (user_id, scope)).fetchone()
    if row["count"] > limit:
        raise ServiceError("rate_limited", MESSAGE, 429)
