"""Opaque DB sessions; bounded, process-local login throttling for one worker."""
import hashlib
import re
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import timedelta
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from backend.persistence import ServiceError, database

COOKIE = "antiplagiat_session"
SESSION_SECONDS = 8 * 60 * 60
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
LOGIN_LIMIT = 10
LOGIN_WINDOW = 300
login_gate = threading.BoundedSemaphore(2)


def valid_username(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", value) is not None


def password_hash(password):
    return HASHER.hash(password)


def token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def public_origin():
    import os
    origin = os.environ.get("ANTIPLAGIAT_PUBLIC_ORIGIN", "http://127.0.0.1:3000")
    parsed = urlsplit(origin)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ServiceError("configuration", "Lokal origin sozlamasi noto‘g‘ri.", 503)
    return origin


def guard(request):
    if (request.url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or not request.client or request.client.host not in {"127.0.0.1", "::1"}
            or request.headers.get("x-antiplagiat-local") != "1"):
        raise ServiceError("local_only", "Faqat lokal interfeys orqali foydalaning.", 403)
    origin = request.headers.get("origin")
    if (origin and origin != public_origin()) or (request.method not in {"GET", "HEAD"} and not origin):
        raise ServiceError("origin", "So‘rov origin tekshiruvidan o‘tmadi.", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise ServiceError("origin", "So‘rov origin tekshiruvidan o‘tmadi.", 403)


class LoginLimiter:
    def __init__(self):
        self.lock, self.attempts = threading.Lock(), {}

    def check(self, peer):
        now = time.monotonic()
        with self.lock:
            # The peer comes from the socket, never X-Forwarded-For.
            for key in list(self.attempts):
                if not self.attempts[key] or self.attempts[key][-1] <= now - LOGIN_WINDOW:
                    del self.attempts[key]
            if peer not in self.attempts and len(self.attempts) >= 1024:
                raise ServiceError("login_limit", "Kirish urinishlari ko‘p. Keyinroq urinib ko‘ring.", 429)
            entries = self.attempts.setdefault(peer, deque())
            while entries and entries[0] <= now - LOGIN_WINDOW:
                entries.popleft()
            if len(entries) >= LOGIN_LIMIT:
                raise ServiceError("login_limit", "Kirish urinishlari ko‘p. Keyinroq urinib ko‘ring.", 429)
            entries.append(now)


limiter = LoginLimiter()


def login(username, password, old_token=None):
    if not login_gate.acquire(blocking=False):
        raise ServiceError("login_limit", "Kirish urinishlari ko‘p. Keyinroq urinib ko‘ring.", 429)
    try:
        with database() as conn:
            row = conn.execute("SELECT id,username,password_hash,role,enabled,can_submit_to_corpus"
                               " FROM antiplagiat.users WHERE username=%s", (username,)).fetchone()
        try:
            HASHER.verify(row["password_hash"] if row else DUMMY_HASH, password)
            valid = bool(row and row["enabled"])
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid:
            raise ServiceError("credentials", "Login yoki parol noto‘g‘ri.", 401)
        token = secrets.token_urlsafe(32)
        with database() as conn:
            # A disabled account or password change during verification cannot sign in.
            current = conn.execute("SELECT id FROM antiplagiat.users WHERE id=%s AND enabled AND password_hash=%s",
                                   (row["id"], row["password_hash"])).fetchone()
            if not current:
                raise ServiceError("credentials", "Login yoki parol noto‘g‘ri.", 401)
            conn.execute("DELETE FROM antiplagiat.sessions WHERE expires_at <= now()")
            if old_token and re.fullmatch(r"[A-Za-z0-9_-]{43}", old_token):
                conn.execute("DELETE FROM antiplagiat.sessions WHERE token_hash=%s", (token_hash(old_token),))
            conn.execute("INSERT INTO antiplagiat.sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+%s)",
                         (token_hash(token), row["id"], timedelta(seconds=SESSION_SECONDS)))
        return token, {"id": str(row["id"]), "username": row["username"], "role": row["role"],
                       "can_submit_to_corpus": row["can_submit_to_corpus"]}
    finally:
        login_gate.release()


def require_user(request):
    guard(request)
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ServiceError("unauthenticated", "Avval hisobingizga kiring.", 401)
    with database() as conn:
        row = conn.execute("SELECT u.id,u.username,u.role,u.can_submit_to_corpus FROM antiplagiat.sessions s"
                           " JOIN antiplagiat.users u ON u.id=s.user_id"
                           " WHERE s.token_hash=%s AND s.expires_at>now() AND u.enabled", (token_hash(token),)).fetchone()
    if not row:
        raise ServiceError("unauthenticated", "Session tugagan. Qayta kiring.", 401)
    return {**row, "id": str(row["id"])}


CORPUS_MANAGEMENT_ROLES = {"admin", "corpus_manager"}
# A teacher is not a separate database role: every ordinary signed-in account
# COULD be a department teacher, since that is this whole platform's audience
# (see docs/decisions.md §12). But submission access is not every "user"
# account's right by default -- an admin grants it per account via the
# can_submit_to_corpus flag (migration 006) -- so this constant only says
# which role is ELIGIBLE to be granted it, not who currently has it.
TEACHER_SUBMISSION_ROLE = "user"


def require_corpus_manager(request):
    # Corpus administration only; it never widens access to personal reports.
    user = require_user(request)
    if user.get("role") not in CORPUS_MANAGEMENT_ROLES:
        raise ServiceError("forbidden", "Bu amal uchun administrator yoki korpus boshqaruvchisi roli kerak.", 403)
    return user


def require_admin(request):
    # Granting/revoking another account's corpus submission access: admin
    # only, narrower than require_corpus_manager -- a corpus_manager curates
    # the corpus itself, not who may propose additions to it.
    user = require_user(request)
    if user.get("role") != "admin":
        raise ServiceError("forbidden", "Bu amal uchun administrator roli kerak.", 403)
    return user


def require_teacher(request):
    # The corpus submission queue only; never widens access to corpus
    # administration or another user's personal reports. admin/corpus_manager
    # pass unconditionally -- they already have their own direct, unmoderated
    # upload path and have no need for the flag. A "user" account needs the
    # admin-granted can_submit_to_corpus flag; every other role is refused.
    user = require_user(request)
    role = user.get("role")
    if role in CORPUS_MANAGEMENT_ROLES:
        return user
    if role == TEACHER_SUBMISSION_ROLE and user.get("can_submit_to_corpus"):
        return user
    raise ServiceError("forbidden", "Bu amal uchun korpusga taklif qilish huquqi kerak.", 403)


def set_corpus_submission_access(user_id, enabled, config=None):
    """Admin-only grant/revoke of can_submit_to_corpus; see corpus_api.py's
    two endpoints that call this. Only ever touches a "user"-role account --
    admin/corpus_manager do not need the flag (require_teacher lets them
    through regardless), and flipping it on a reviewer account would be
    silently meaningless, so it is refused instead.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "UPDATE antiplagiat.users SET can_submit_to_corpus=%s"
            " WHERE id=%s AND role=%s RETURNING id,username,can_submit_to_corpus",
            (bool(enabled), user_id, TEACHER_SUBMISSION_ROLE)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi yoki oddiy foydalanuvchi emas.", 404)
    return {"id": str(row["id"]), "username": row["username"],
           "can_submit_to_corpus": row["can_submit_to_corpus"]}


def logout(request):
    require_user(request)
    with database() as conn:
        conn.execute("DELETE FROM antiplagiat.sessions WHERE token_hash=%s", (token_hash(request.cookies[COOKIE]),))
