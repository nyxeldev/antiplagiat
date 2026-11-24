"""Opaque DB sessions; bounded, process-local login throttling for one worker."""
import hashlib
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections import deque
from datetime import timedelta
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from psycopg.errors import UniqueViolation

from backend.persistence import ServiceError, database

COOKIE = "antiplagiat_session"
SESSION_SECONDS = 8 * 60 * 60
# roles-phase1 (docs/decisions.md Sect.25): profil rasmi. Qayta kodlash/resize
# yo'q (Pillow ataylab qo'shilmagan) -- shu sababli qattiq, kichik hajm
# chegarasi birinchi himoya qatlami.
MAX_AVATAR_BYTES = 1024 * 1024
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
            row = conn.execute("SELECT id,username,password_hash,role,enabled,can_submit_to_corpus,kafedra_id"
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
                       "can_submit_to_corpus": row["can_submit_to_corpus"],
                       "kafedra_id": str(row["kafedra_id"]) if row["kafedra_id"] else None}
    finally:
        login_gate.release()


def require_user(request):
    guard(request)
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ServiceError("unauthenticated", "Avval hisobingizga kiring.", 401)
    with database() as conn:
        row = conn.execute("SELECT u.id,u.username,u.role,u.can_submit_to_corpus,u.kafedra_id FROM antiplagiat.sessions s"
                           " JOIN antiplagiat.users u ON u.id=s.user_id"
                           " WHERE s.token_hash=%s AND s.expires_at>now() AND u.enabled", (token_hash(token),)).fetchone()
    if not row:
        raise ServiceError("unauthenticated", "Session tugagan. Qayta kiring.", 401)
    return {**row, "id": str(row["id"]), "kafedra_id": str(row["kafedra_id"]) if row["kafedra_id"] else None}


# roles-phase1 (docs/decisions.md Sect.18): besh rolli model. Eski to'rt rolli
# model (user/reviewer/corpus_manager/admin) migratsiya 008 orqali shu
# beshtaga aniq ko'chirildi. Kafedra bo'yicha QAMROV (2-faza, docs/decisions.md
# Sect.19) endi korpus hujjatlari darajasida ishlaydi -- backend/corpus.py'dagi
# manager_scope(); kafedra_mudiri endi faqat o'z kafedrasi + kafedrasiz
# ("umumiy") hujjatlarni ko'radi, admin/super_admin hamon hammasini ko'radi.
# /compare orqali solishtirish (candidates()) bundan MUSTASNO -- u hamon
# butun korpusni qidiradi, ataylab (qarang Sect.19).
ROLES = ("talaba", "ustoz", "kafedra_mudiri", "admin", "super_admin")

# kafedra_mudiri eski corpus_manager'ning o'rniga keldi; admin/super_admin
# ikkisi ham korpusni to'liq boshqaradi (super_admin faqat CLI orqali
# tayinlanadi, lekin tayinlangandan keyin admin bilan bir xil huquqga ega).
CORPUS_MANAGEMENT_ROLES = {"admin", "super_admin", "kafedra_mudiri"}
# require_admin esa shundan ham torroq -- kafedra_mudiri korpusni boshqaradi,
# lekin boshqa akkauntning taklif huquqini bera olmaydi (shu quyidagi
# ADMIN_ROLES bilan ajratiladi).
ADMIN_ROLES = {"admin", "super_admin"}
# "ustoz" roli endi alohida database roli -- eski modelda bu "user" + flag
# edi. Lekin submission huquqi hamon har bir "ustoz" akkauntining avtomatik
# huquqi EMAS -- admin uni can_submit_to_corpus flag orqali (migratsiya 006)
# alohida yoqadi/o'chiradi -- shu sababli bu konstant faqat qaysi ROL bu
# flagga ERISHISHI mumkinligini bildiradi, kim hozir unga ega ekanini emas.
TEACHER_SUBMISSION_ROLE = "ustoz"


def require_corpus_manager(request):
    # Corpus administration only; it never widens access to personal reports.
    user = require_user(request)
    if user.get("role") not in CORPUS_MANAGEMENT_ROLES:
        raise ServiceError("forbidden", "Bu amal uchun administrator yoki korpus boshqaruvchisi roli kerak.", 403)
    return user


def require_admin(request):
    # Granting/revoking another account's corpus submission access: admin
    # (yoki super_admin) only, narrower than require_corpus_manager --
    # kafedra_mudiri korpusning o'zini kuratsiya qiladi, lekin unga kimning
    # taklif kiritishini belgilay olmaydi.
    user = require_user(request)
    if user.get("role") not in ADMIN_ROLES:
        raise ServiceError("forbidden", "Bu amal uchun administrator roli kerak.", 403)
    return user


def require_teacher(request):
    # The corpus submission queue only; never widens access to corpus
    # administration or another user's personal reports. admin/super_admin/
    # kafedra_mudiri pass unconditionally -- they already have their own
    # direct, unmoderated upload path and have no need for the flag. An
    # "ustoz" account needs the admin-granted can_submit_to_corpus flag;
    # every other role (talaba included) is refused.
    user = require_user(request)
    role = user.get("role")
    if role in CORPUS_MANAGEMENT_ROLES:
        return user
    if role == TEACHER_SUBMISSION_ROLE and user.get("can_submit_to_corpus"):
        return user
    raise ServiceError("forbidden", "Bu amal uchun korpusga taklif qilish huquqi kerak.", 403)


def set_corpus_submission_access(user_id, enabled, config=None):
    """Admin-only grant/revoke of can_submit_to_corpus; see corpus_api.py's
    two endpoints that call this. Only ever touches an "ustoz"-role account --
    admin/super_admin/kafedra_mudiri do not need the flag (require_teacher
    lets them through regardless), and flipping it on a talaba account would
    be silently meaningless, so it is refused instead.
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
        raise ServiceError("not_found", "Foydalanuvchi topilmadi yoki ustoz emas.", 404)
    return {"id": str(row["id"]), "username": row["username"],
           "can_submit_to_corpus": row["can_submit_to_corpus"]}


def set_role(user_id, role, config=None):
    """Admin panel (roles-phase1 3-bosqich, docs/decisions.md Sect.20) role
    reassignment by id. super_admin is refused here on purpose -- the runtime
    DB grant alone does not stop it, so this is the one place that does;
    manage.py assign_role (CLI, privileged DB password) stays the only way.
    """
    if role not in ROLES or role == "super_admin":
        raise ServiceError("validation_error", "Noma'lum yoki ruxsat etilmagan rol.", 400)
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute("UPDATE antiplagiat.users SET role=%s WHERE id=%s RETURNING id,username,role",
                           (role, user_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"]}


def set_kafedra(user_id, qisqa_kodi, config=None):
    """Admin panel (roles-phase1 3-bosqich) kafedra assignment by id. An
    empty/missing qisqa_kodi clears the assignment (kafedra_id=NULL, "umumiy"
    scope) -- the existing CLI departments.assign_user() has no such path, it
    only ever assigns to a real kafedra, so this is a separate implementation
    rather than a shared one. Existence is checked explicitly rather than
    relying on the FK violation, so a bad code is a clean 404, not a
    persistence.database()-sanitized 503.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        kafedra_id = None
        if qisqa_kodi:
            kafedra = conn.execute("SELECT id FROM antiplagiat.kafedra WHERE qisqa_kodi=%s",
                                   (qisqa_kodi.strip(),)).fetchone()
            if not kafedra:
                raise ServiceError("not_found", "Bunday qisqa koddagi kafedra topilmadi.", 404)
            kafedra_id = kafedra["id"]
        row = conn.execute("UPDATE antiplagiat.users SET kafedra_id=%s WHERE id=%s RETURNING id,username,kafedra_id",
                           (kafedra_id, user_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "username": row["username"],
           "kafedra_id": str(row["kafedra_id"]) if row["kafedra_id"] else None}


def set_enabled(user_id, enabled, actor_id, config=None):
    """Admin panel (roles-phase1 Sect.23) account enable/disable -- previously
    the `users.enabled` column existed and was already enforced at login
    (login()) and session validation (validate_session(), both WHERE u.enabled)
    but nothing anywhere could ever set it to false; this is that missing
    write path. Disabling takes effect immediately on the next request from
    that account (no separate session purge needed -- validate_session()
    already re-checks u.enabled every time).

    Self-disable is refused: an admin locking out their own only working
    account, with no one else around to re-enable it, is a foot-gun this
    function closes rather than one the UI merely discourages.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    if not enabled and user_id == str(actor_id):
        raise ServiceError("validation_error", "O‘z akkauntingizni o‘chira olmaysiz.", 400)
    with database(config) as conn:
        row = conn.execute("UPDATE antiplagiat.users SET enabled=%s WHERE id=%s RETURNING id,username,enabled",
                           (bool(enabled), user_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "username": row["username"], "enabled": row["enabled"]}


def change_password(user_id, old_password, new_password, config=None):
    """Self-service password change -- roles-phase1 Sect.24. Every role calls
    this on their OWN account only (user_id always comes from require_user(),
    never a path/body parameter -- see accounts_api.py); there is no "change
    someone else's password" path here, that stays manage.py create-user's
    sibling CLI command plus a brand-new account, out of scope for this.

    The current password is required, same reasoning as any ordinary
    change-password flow: a hijacked-but-still-logged-in session should not
    be able to silently lock the real owner out by swapping the password
    unchallenged.

    Every session for this account (including the one making this very
    request) is deleted once the password changes -- a stale session token
    captured earlier must not keep working after the owner believes they have
    rotated it away. The frontend is expected to treat the 401 on its next
    request the same as any other expired session (see useSessionExpired()).
    """
    from backend.manage import MAX_PASSWORD_CHARS, MIN_PASSWORD_CHARS, weak_password_reason
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute("SELECT username,password_hash FROM antiplagiat.users WHERE id=%s", (user_id,)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    try:
        HASHER.verify(row["password_hash"], old_password)
    except (VerificationError, InvalidHashError):
        raise ServiceError("credentials", "Joriy parol noto‘g‘ri.", 401) from None
    if not isinstance(new_password, str) or not MIN_PASSWORD_CHARS <= len(new_password) <= MAX_PASSWORD_CHARS:
        raise ServiceError("validation_error", f"Yangi parol {MIN_PASSWORD_CHARS}-{MAX_PASSWORD_CHARS} belgi bo‘lishi kerak.", 400)
    weak = weak_password_reason(new_password, row["username"])
    if weak:
        raise ServiceError("validation_error", f"Juda sodda parol: {weak}.", 400)
    hashed = password_hash(new_password)
    with database(config) as conn:
        conn.execute("UPDATE antiplagiat.users SET password_hash=%s WHERE id=%s", (hashed, user_id))
        conn.execute("DELETE FROM antiplagiat.sessions WHERE user_id=%s", (user_id,))
    return {"status": "changed"}


def logout(request):
    require_user(request)
    with database() as conn:
        conn.execute("DELETE FROM antiplagiat.sessions WHERE token_hash=%s", (token_hash(request.cookies[COOKIE]),))


def get_profile(user_id, config=None):
    """Full self-profile for GET /auth/me (roles-phase1 Sect.25) -- heavier
    than require_user()'s per-request check (one extra kafedra join), so it
    is deliberately NOT used for require_user's own hot-path query, only for
    the one-off "who am I, in full" read the profile page needs.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.role, u.can_submit_to_corpus, u.kafedra_id, u.full_name,"
            " u.created_at, (u.avatar IS NOT NULL) AS has_avatar, k.nomi AS kafedra_nomi"
            " FROM antiplagiat.users u LEFT JOIN antiplagiat.kafedra k ON k.id = u.kafedra_id"
            " WHERE u.id=%s", (user_id,)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"],
           "can_submit_to_corpus": row["can_submit_to_corpus"],
           "kafedra_id": str(row["kafedra_id"]) if row["kafedra_id"] else None,
           "kafedra_nomi": row["kafedra_nomi"], "full_name": row["full_name"],
           "created_at": row["created_at"].isoformat(), "has_avatar": row["has_avatar"]}


def set_full_name(user_id, full_name, config=None):
    """Self-service full-name edit (roles-phase1 Sect.25). An empty/blank
    value CLEARS the name (full_name=NULL) rather than being refused -- a
    user who set a name and changed their mind should be able to go back to
    plain username display without typing a placeholder.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    if not isinstance(full_name, str):
        raise ServiceError("validation_error", "full_name satr bo‘lishi kerak.", 400)
    cleaned = full_name.strip()
    if cleaned and any(unicodedata.category(c).startswith("C") for c in cleaned):
        raise ServiceError("validation_error", "To‘liq ism boshqaruv belgilarini o‘z ichiga ololmaydi.", 400)
    if cleaned and not 1 <= len(cleaned) <= 120:
        raise ServiceError("validation_error", "To‘liq ism 1-120 belgi bo‘lishi kerak.", 400)
    with database(config) as conn:
        row = conn.execute("UPDATE antiplagiat.users SET full_name=%s WHERE id=%s RETURNING id,full_name",
                           (cleaned or None, user_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "full_name": row["full_name"]}


def set_username(user_id, new_username, config=None):
    """Self-service login (username) change (roles-phase1 Sect.25). Same
    valid_username() shape as account creation and the DB CHECK constraint.
    A taken login is a clean 409, caught inside the transaction exactly like
    manage.py's create_user() catches the same UniqueViolation -- it must be
    turned into a non-psycopg.Error here, or persistence.database() would
    otherwise flatten it into an opaque "database unavailable" 503.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    if not valid_username(new_username):
        raise ServiceError("validation_error", "Login: 3-64 kichik lotin harfi/son/_.- bo‘lishi kerak.", 400)
    with database(config) as conn:
        try:
            row = conn.execute("UPDATE antiplagiat.users SET username=%s WHERE id=%s RETURNING id,username",
                               (new_username, user_id)).fetchone()
        except UniqueViolation:
            raise ServiceError("validation_error", "Bu login allaqachon band.", 409) from None
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"id": str(row["id"]), "username": row["username"]}


def _sniff_image_mime(raw):
    """No Pillow (docs/decisions.md Sect.25): a cheap magic-byte check rather
    than a real decode. This only rejects obviously-wrong content; it is not
    a substitute for the browser-side X-Content-Type-Options: nosniff header
    that get_avatar's caller sets when serving the bytes back.
    """
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def set_avatar(user_id, raw, config=None):
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise ServiceError("file_limit", "Rasm 1 MiB dan oshmasligi kerak.", 413)
    mime = _sniff_image_mime(bytes(raw))
    if not mime:
        raise ServiceError("unsupported", "Faqat PNG, JPEG yoki WEBP rasm qabul qilinadi.", 415)
    with database(config) as conn:
        row = conn.execute("UPDATE antiplagiat.users SET avatar=%s, avatar_mime=%s WHERE id=%s RETURNING id",
                           (raw, mime, user_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"status": "updated", "has_avatar": True}


def clear_avatar(user_id, config=None):
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute("UPDATE antiplagiat.users SET avatar=NULL, avatar_mime=NULL WHERE id=%s RETURNING id",
                           (user_id,)).fetchone()
    if not row:
        raise ServiceError("not_found", "Foydalanuvchi topilmadi.", 404)
    return {"status": "cleared", "has_avatar": False}


def get_avatar(user_id, config=None):
    """Returns (raw_bytes, mime). Deliberately the SAME 404 whether the
    account does not exist or simply has no avatar set -- the existing
    no-existence-leak pattern (see set_kafedra's docstring) applied here so a
    random uuid cannot be used to probe which accounts exist.
    """
    try:
        user_id = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("not_found", "Rasm topilmadi.", 404) from None
    with database(config) as conn:
        row = conn.execute("SELECT avatar, avatar_mime FROM antiplagiat.users WHERE id=%s", (user_id,)).fetchone()
    if not row or row["avatar"] is None:
        raise ServiceError("not_found", "Rasm topilmadi.", 404)
    return bytes(row["avatar"]), row["avatar_mime"]


def list_sessions(user_id, current_token, config=None):
    """Self-service "where am I logged in" (roles-phase1 Sect.25). token_hash
    is never returned to the client -- only a per-row is_current flag,
    computed by comparing hashes server-side the same way logout() finds its
    own session.
    """
    current_hash = token_hash(current_token) if current_token else None
    with database(config) as conn:
        rows = conn.execute(
            "SELECT token_hash, created_at, expires_at FROM antiplagiat.sessions"
            " WHERE user_id=%s AND expires_at>now() ORDER BY created_at DESC", (user_id,)).fetchall()
    return {"items": [{"created_at": row["created_at"].isoformat(), "expires_at": row["expires_at"].isoformat(),
                       "is_current": row["token_hash"] == current_hash} for row in rows]}


def revoke_other_sessions(user_id, current_token, config=None):
    """Sign out of every OTHER session (roles-phase1 Sect.25) -- the current
    one (the request making this very call) is deliberately kept alive,
    unlike change_password()'s full purge, since nothing about the account's
    credentials changed here.
    """
    with database(config) as conn:
        conn.execute("DELETE FROM antiplagiat.sessions WHERE user_id=%s AND token_hash<>%s",
                     (user_id, token_hash(current_token)))
    return {"status": "revoked"}
