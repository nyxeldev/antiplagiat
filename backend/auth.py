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
