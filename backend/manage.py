"""python -m backend.manage migrate / create-user.

All database/account passwords are read with getpass in a local terminal.
Never load .env, accept passwords as arguments or print raw database errors.
"""
import argparse
import getpass
import hashlib
import logging
import os
import re
import sys
import uuid
import warnings
from pathlib import Path

from psycopg import sql
from psycopg.errors import UniqueViolation

from backend.persistence import ServiceError, database

# Local development setting, lowered on the owner's instruction. A pilot
# deployment must raise this again before real accounts are created.
MIN_PASSWORD_CHARS = 4
MAX_PASSWORD_CHARS = 256


class MigrationError(Exception):
    """Safe actionable migration errors, separate from raw driver errors."""


class UsernameTakenError(Exception):
    """CLI domain error; must not inherit ValueError or psycopg.Error."""


class MigrationDiagnostics:
    """CLI-only allowlisted metadata; never stores exception text or SQL values."""
    def __init__(self):
        self.stage, self.step = "configuration", "prompt_database"
        self.exception_class, self.sqlstate = "none", "-"

    def mark(self, stage, step):
        self.stage = stage
        self.step = step if re.fullmatch(r"[A-Za-z0-9_]{1,80}", step) else "migration_file"

    def __call__(self, stage, error=None):
        if error is not None:
            self.record(error)
        elif stage:
            self.mark(stage, {"configuration": "database_settings", "connect": "database_connect",
                              "commit": "transaction_commit"}[stage])

    def record(self, error):
        # Keep the original error captured before database() wraps it in ServiceError.
        if self.exception_class != "none":
            return
        name = type(error).__name__
        self.exception_class = name if re.fullmatch(r"[A-Za-z0-9_]{1,80}", name) else "Exception"
        code = getattr(error, "sqlstate", None)
        self.sqlstate = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else "-"

    def summary(self):
        return f"diagnostic: stage={self.stage} exception={self.exception_class} sqlstate={self.sqlstate} step={self.step}"


def migration_step(conn, diagnostic, stage, step, statement, parameters=None):
    if diagnostic:
        diagnostic.mark(stage, step)
    return conn.execute(statement, parameters) if parameters is not None else conn.execute(statement)


def migration_files(diagnostic):
    if diagnostic:
        diagnostic.mark("configuration", "migration_files")
    files = [(p.stem, p.read_text(encoding="utf-8"))
             for p in sorted((Path(__file__).parent / "migrations").glob("*.sql"))]
    if not files:
        raise MigrationError("Migratsiya SQL fayllari topilmadi.")
    return files


def migration_preflight(conn, runtime_role, files, diagnostic):
    def query(step, statement, parameters=None):
        return migration_step(conn, diagnostic, "preflight", step, statement, parameters)
    principal = query("current_user", "SELECT current_user AS name").fetchone()["name"]
    if principal == runtime_role:
        raise MigrationError("Migratsiya runtime hisobidan alohida vakolatli hisobni talab qiladi.")
    role = query("runtime_role", "SELECT rolsuper FROM pg_roles WHERE rolname = %s", (runtime_role,)).fetchone()
    owner = query("database_owner", "SELECT pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname=current_database()").fetchone()
    if not role or role["rolsuper"] or owner["owner"] == runtime_role:
        raise MigrationError("Runtime hisobi mavjud, superuser bo‘lmagan va DB egasi bo‘lmagan hisob bo‘lishi kerak.")
    can_create = query("database_create", "SELECT has_database_privilege(current_user,current_database(),'CREATE') AS allowed").fetchone()["allowed"]
    schema = query("schema_privileges", "SELECT has_schema_privilege(current_user,oid,'CREATE') AS can_create FROM pg_namespace WHERE nspname='antiplagiat'").fetchone()
    if (schema and not schema["can_create"]) or (not schema and not can_create):
        raise MigrationError("Migratsiya sxemasi uchun zarur CREATE huquqi yo‘q.")
    exists = query("migration_table", "SELECT to_regclass('antiplagiat.schema_migrations') IS NOT NULL AS present").fetchone()["present"]
    applied = {}
    if exists:
        applied = {r["version"]: r["checksum"] for r in query("read_versions", "SELECT version,checksum FROM antiplagiat.schema_migrations")}
    if diagnostic:
        diagnostic.mark("preflight", "checksum_validation")
    known = {version for version, _ in files}
    if applied.keys() - known:
        raise MigrationError("Bazada ushbu kod tanimaydigan migratsiya bor.")
    for version, content in files:
        if version in applied and applied[version] != hashlib.sha256(content.encode()).hexdigest():
            raise MigrationError("Bajarilgan migratsiya o‘zgargan; yangi versiya yarating.")
    pending_objects = {
        "001_accounts_reports": [
            ("initial_users", "SELECT to_regclass('antiplagiat.users') IS NOT NULL AS present"),
            ("initial_sessions", "SELECT to_regclass('antiplagiat.sessions') IS NOT NULL AS present"),
            ("initial_reports", "SELECT to_regclass('antiplagiat.reports') IS NOT NULL AS present"),
            ("initial_guard_report", "SELECT to_regprocedure('antiplagiat.guard_report()') IS NOT NULL AS present"),
        ],
        "002_internal_corpus": [
            ("corpus_documents", "SELECT to_regclass('antiplagiat.corpus_documents') IS NOT NULL AS present"),
            ("corpus_chunks", "SELECT to_regclass('antiplagiat.corpus_chunks') IS NOT NULL AS present"),
            ("corpus_guard", "SELECT to_regprocedure('antiplagiat.guard_corpus_document()') IS NOT NULL AS present"),
        ],
        "003_uz_latin_v3_index": [
            ("corpus_chunks_v3_column",
             "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='antiplagiat' "
             "AND table_name='corpus_chunks' AND column_name='chunk_text_uz_latin_v3') AS present"),
            ("corpus_chunks_fts_v3_index", "SELECT to_regclass('antiplagiat.corpus_chunks_fts_v3') IS NOT NULL AS present"),
        ],
        "004_corpus_visibility": [
            ("corpus_documents_visibility_column",
             "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='antiplagiat' "
             "AND table_name='corpus_documents' AND column_name='visibility') AS present"),
        ],
        "005_corpus_moderation": [
            ("corpus_documents_review_status_column",
             "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='antiplagiat' "
             "AND table_name='corpus_documents' AND column_name='review_status') AS present"),
        ],
    }
    for version, probes in pending_objects.items():
        if version not in known or version in applied:
            continue
        for step, statement in probes:
            if query(step, statement).fetchone()["present"]:
                raise MigrationError("Migratsiya yaratadigan obyekt allaqachon mavjud; avtomatik almashtirish bajarilmaydi.")
    return applied


def hidden_password(prompt):
    # Fail closed instead of getpass echoing redirected stdin.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass(prompt)
    except getpass.GetPassWarning:
        raise ValueError("Parolni yashirish imkoni yo‘q. Interaktiv lokal terminaldan foydalaning.") from None


def prompt_database():
    config = {}
    for key, suffix, default in [("host", "HOST", "127.0.0.1"), ("port", "PORT", "5432"),
                                 ("dbname", "NAME", "antiplagiat"), ("user", "USER", "")]:
        default = os.environ.get("ANTIPLAGIAT_DB_" + suffix, default) if key != "user" else default
        value = input(f"DB {key} [{default}]: ").strip() or default
        if not value:
            raise ValueError("Vakolatli DB hisobini kiriting.")
        config[key] = value
    config["password"] = hidden_password("Vakolatli DB hisobi paroli: ")
    return config


def migrate(config, runtime_role="antiplagiat_app", *, check=False, diagnostic=None):
    with database(config, diagnostic=diagnostic) as conn:
        files = migration_files(diagnostic)
        if check:
            migration_step(conn, diagnostic, "preflight", "read_only", "SET TRANSACTION READ ONLY")
            migration_preflight(conn, runtime_role, files, diagnostic)
        else:
            migration_step(conn, diagnostic, "preflight", "migration_lock", "SELECT pg_advisory_xact_lock(71920261013)")
            applied = migration_preflight(conn, runtime_role, files, diagnostic)
            migration_step(conn, diagnostic, "migration", "create_schema", "CREATE SCHEMA IF NOT EXISTS antiplagiat")
            migration_step(conn, diagnostic, "migration", "create_version_table", "CREATE TABLE IF NOT EXISTS antiplagiat.schema_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
            for version, content in files:
                if version in applied:
                    continue
                migration_step(conn, diagnostic, "migration", version, content)
                migration_step(conn, diagnostic, "migration", "record_version", "INSERT INTO antiplagiat.schema_migrations(version, checksum) VALUES (%s,%s)",
                               (version, hashlib.sha256(content.encode()).hexdigest()))
            ident = sql.Identifier(runtime_role)
            for step, statement in [
                ("schema_revoke", "REVOKE ALL ON SCHEMA antiplagiat FROM PUBLIC, {}"),
                ("tables_revoke", "REVOKE ALL ON ALL TABLES IN SCHEMA antiplagiat FROM PUBLIC, {}"),
                ("schema_usage", "GRANT USAGE ON SCHEMA antiplagiat TO {}"),
                ("users_select", "GRANT SELECT ON antiplagiat.users TO {}"),
                ("sessions_access", "GRANT SELECT, INSERT, DELETE ON antiplagiat.sessions TO {}"),
                ("reports_access", "GRANT SELECT, INSERT ON antiplagiat.reports TO {}"),
                ("reports_purge", "GRANT UPDATE(snapshot, deleted_at) ON antiplagiat.reports TO {}"),
                ("corpus_documents_access", "GRANT SELECT, INSERT ON antiplagiat.corpus_documents TO {}"),
                ("corpus_documents_withdraw", "GRANT UPDATE(status, withdrawn_at, updated_at, extracted_text) ON antiplagiat.corpus_documents TO {}"),
                ("corpus_documents_moderate", "GRANT UPDATE(review_status, rejection_reason) ON antiplagiat.corpus_documents TO {}"),
                ("corpus_chunks_access", "GRANT SELECT, INSERT ON antiplagiat.corpus_chunks TO {}"),
                ("corpus_chunks_purge", "GRANT UPDATE(chunk_text, chunk_text_uz_latin_v3) ON antiplagiat.corpus_chunks TO {}"),
            ]:
                migration_step(conn, diagnostic, "migration", step, sql.SQL(statement).format(ident))
            for step, statement in [
                ("function_revoke", "REVOKE ALL ON FUNCTION antiplagiat.guard_report() FROM PUBLIC"),
                ("corpus_function_revoke", "REVOKE ALL ON FUNCTION antiplagiat.guard_corpus_document() FROM PUBLIC"),
            ]:
                migration_step(conn, diagnostic, "migration", step, statement)
    if check and diagnostic:
        diagnostic.mark("preflight", "check_complete")
    return len(files)


def create_user(config, username, password, role="user"):
    from backend.auth import password_hash, valid_username
    if not valid_username(username) or not MIN_PASSWORD_CHARS <= len(password) <= MAX_PASSWORD_CHARS:
        raise ValueError(f"Login: 3–64 kichik lotin harfi/son/_.-; "
                         f"parol: {MIN_PASSWORD_CHARS}–{MAX_PASSWORD_CHARS} belgi.")
    user_id = uuid.uuid4()
    hashed = password_hash(password)
    with database(config) as conn:
        try:
            conn.execute("INSERT INTO antiplagiat.users(id,username,password_hash,role) VALUES (%s,%s,%s,%s)",
                         (user_id, username, hashed, role))
        except UniqueViolation as error:
            if (error.diag.schema_name == "antiplagiat" and error.diag.table_name == "users"
                    and error.diag.constraint_name == "users_username_key"):
                raise UsernameTakenError("Bu login allaqachon band.") from None
            raise
    return user_id


def corpus_manager_user_id(config, username):
    from backend.auth import CORPUS_MANAGEMENT_ROLES
    with database(config) as conn:
        row = conn.execute("SELECT id, role FROM antiplagiat.users WHERE username=%s AND enabled",
                           (username,)).fetchone()
    if not row:
        raise ValueError("Bunday faol akkaunt topilmadi.")
    if row["role"] not in CORPUS_MANAGEMENT_ROLES:
        raise ValueError("Korpusni faqat admin yoki corpus_manager roli boshqaradi.")
    return row["id"]


CORPUS_UPLOAD_SUFFIXES = (".txt", ".docx", ".pdf")


def _ingest_one(config, source, metadata, uploaded_by):
    """Extract one already-validated file in the sandboxed worker, then store it.

    Shared by corpus_add (single file, interactive) and corpus_add_batch (many
    files, one failure must not stop the rest) so both go through the exact
    same extraction/storage path -- never a separate, untested shortcut.
    """
    import shutil
    import tempfile
    from backend import corpus
    from backend.comparison.runner import run_worker

    with tempfile.TemporaryDirectory(prefix="antiplagiat-corpus-cli-") as directory:
        folder = Path(directory)
        shutil.copyfile(source, folder / "corpus-upload")
        extracted = run_worker(folder, {"mode": "extract",
                                        "items": [{"path": "corpus-upload", "name": source.name}]})
        raw = (folder / "corpus-upload").read_bytes()
        return corpus.add_document(metadata, extracted["documents"][0], uploaded_by, raw, config)


def corpus_add(config, path, username):
    """Parse the file in the sandboxed worker, then store it with its permission basis."""
    from backend import corpus

    source = Path(path)
    if not source.is_file():
        raise ValueError("Fayl topilmadi.")
    uploaded_by = corpus_manager_user_id(config, username)
    metadata = {
        "title": input("Sarlavha: ").strip(),
        "author_display": input("Muallif (ko‘rsatiladigan nom): ").strip(),
        "doc_type": input(f"Turi ({'/'.join(corpus.DOC_TYPES)}): ").strip(),
        "language_hint": input("Til belgisi [uz]: ").strip() or "uz",
        "source_note": input("Manba izohi (ixtiyoriy): ").strip(),
        "permission_basis": input("Ruxsat asosi (majburiy): ").strip(),
        "visibility": input("Ko‘rinish (excerpt/metadata_only) [excerpt]: ").strip() or "excerpt",
        "original_filename": source.name,
    }
    year = input("Yil (ixtiyoriy): ").strip()
    metadata["year"] = int(year) if year.isdecimal() else None
    problems = corpus.metadata_errors(metadata)
    if problems:
        raise ValueError(" ".join(problems))
    return _ingest_one(config, source, metadata, uploaded_by)


def _expand_batch_paths(paths):
    """Each entry may be a file or a directory (non-recursive: only files
    directly inside it, sorted for a deterministic, reproducible order).
    A directory contributes only its TXT/DOCX/PDF files silently (mixed
    directories are normal); a FILE path the caller named explicitly is kept
    as-is even with an unsupported suffix, so it surfaces as a per-file error
    below rather than being silently dropped.
    """
    files = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_dir():
            files.extend(sorted(p for p in candidate.iterdir()
                               if p.is_file() and p.suffix.lower() in CORPUS_UPLOAD_SUFFIXES))
        else:
            files.append(candidate)
    return files


def corpus_add_batch(config, paths, username):
    """Ingest many files/folders in one run: shared metadata, one result per
    file (added / duplicate / error), one bad file never stops the rest.
    """
    from backend import corpus

    uploaded_by = corpus_manager_user_id(config, username)
    files = _expand_batch_paths(paths)
    if not files:
        raise ValueError("Birorta ham fayl topilmadi.")
    shared = {
        "author_display": input("Muallif (ko‘rsatiladigan nom, butun partiya uchun): ").strip(),
        "doc_type": input(f"Turi ({'/'.join(corpus.DOC_TYPES)}, butun partiya uchun): ").strip(),
        "language_hint": input("Til belgisi [uz]: ").strip() or "uz",
        "source_note": input("Manba izohi (ixtiyoriy, butun partiya uchun): ").strip(),
        "permission_basis": input("Ruxsat asosi (majburiy, butun partiya uchun): ").strip(),
        "visibility": input("Ko‘rinish (excerpt/metadata_only, butun partiya uchun) [excerpt]: ").strip() or "excerpt",
    }
    if not shared["permission_basis"]:
        raise ValueError("Ruxsat asosi majburiy; usiz hech bir hujjat korpusga kirmaydi.")
    year_input = input("Yil (ixtiyoriy, butun partiya uchun): ").strip()
    shared["year"] = int(year_input) if year_input.isdecimal() else None

    results = []
    for source in files:
        result = {"path": str(source)}
        try:
            if not source.is_file():
                raise ValueError("Fayl topilmadi.")
            if source.suffix.lower() not in CORPUS_UPLOAD_SUFFIXES:
                raise ValueError("Faqat TXT, DOCX va PDF qabul qilinadi: " + source.suffix)
            metadata = {**shared, "title": source.stem, "original_filename": source.name}
            problems = corpus.metadata_errors(metadata)
            if problems:
                raise ValueError(" ".join(problems))
            stored = _ingest_one(config, source, metadata, uploaded_by)
            result.update(status="added", id=stored["id"], chunk_count=stored["chunk_count"])
        except ServiceError as error:
            result.update(status="duplicate" if error.code == "corpus_duplicate" else "error",
                          code=error.code, message=error.message)
        except Exception as error:
            result.update(status="error", code=getattr(error, "code", None),
                          message=getattr(error, "message", str(error)))
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    migration = sub.add_parser("migrate")
    migration.add_argument("--runtime-role", default="antiplagiat_app")
    migration.add_argument("--check", action="store_true", help="Faqat read-only ulanish/preflight; DDL va grants bajarilmaydi.")
    migration.add_argument("--diagnostic", action="store_true", help="Faqat xavfsiz bosqich/exception klassi/SQLSTATE/qadamni chiqarish.")
    account = sub.add_parser("create-user")
    account.add_argument("username")
    account.add_argument("--role", choices=["user", "reviewer", "corpus_manager", "admin"], default="user")
    add_corpus = sub.add_parser("corpus-add")
    add_corpus.add_argument("path", help="Lokal TXT/DOCX/matnli PDF fayl yo‘li.")
    add_corpus.add_argument("--as-user", required=True, help="Korpusni boshqaradigan admin yoki corpus_manager login.")
    add_corpus_batch = sub.add_parser("corpus-add-batch")
    add_corpus_batch.add_argument("paths", nargs="+",
                                  help="Bir yoki bir nechta lokal TXT/DOCX/PDF fayl yoki papka yo‘li.")
    add_corpus_batch.add_argument("--as-user", required=True,
                                  help="Korpusni boshqaradigan admin yoki corpus_manager login.")
    show_corpus = sub.add_parser("corpus-list")
    show_corpus.add_argument("--page", type=int, default=1)
    show_corpus.add_argument("--status", choices=["active", "withdrawn", "all"], default="active")
    drop_corpus = sub.add_parser("corpus-withdraw")
    drop_corpus.add_argument("document_id")
    args = parser.parse_args()
    diagnostic = MigrationDiagnostics() if args.command == "migrate" and args.diagnostic else None
    driver_logger = logging.getLogger("psycopg")
    previous_log_level = driver_logger.level
    if diagnostic:
        # psycopg __exit__ can log raw rollback errors; CLI emits only safe metadata.
        driver_logger.setLevel(logging.CRITICAL + 1)
    try:
        config = prompt_database()
        if args.command == "migrate":
            count = migrate(config, args.runtime_role, check=args.check, diagnostic=diagnostic)
            print("Preflight: PASS (read-only; migratsiya qo‘llanmadi)." if args.check else f"Migratsiyalar tayyor: {count}; runtime huquqlari cheklangan.")
            if diagnostic:
                print(diagnostic.summary())
        elif args.command == "corpus-add":
            stored = corpus_add(config, args.path, getattr(args, "as_user"))
            print(f"Korpusga qo‘shildi: {stored['id']}; chunk: {stored['chunk_count']}, token: {stored['token_count']}.")
        elif args.command == "corpus-add-batch":
            results = corpus_add_batch(config, args.paths, getattr(args, "as_user"))
            for result in results:
                if result["status"] == "added":
                    print(f"QO‘SHILDI   {result['path']}  ({result['id']}, {result['chunk_count']} chunk)")
                elif result["status"] == "duplicate":
                    print(f"DUBLIKAT    {result['path']}  {result['message']}")
                else:
                    print(f"XATO        {result['path']}  {result['message']}")
            counts = {status: sum(1 for r in results if r["status"] == status)
                     for status in ("added", "duplicate", "error")}
            print(f"Jami: {len(results)}; qo‘shildi {counts['added']}, dublikat {counts['duplicate']}, "
                  f"xato {counts['error']}.")
            if counts["error"]:
                sys.exit(1)
        elif args.command == "corpus-list":
            from backend import corpus
            page = corpus.list_documents(args.page, args.status, config)
            for item in page["items"]:
                year = item["year"] or "-"
                print(f"{item['id']}  {item['status']:9} {year:>4}  {item['doc_type']:14} {item['title']}")
            print(f"{len(page['items'])} ta yozuv; sahifa {page['page']}; keyingi sahifa: "
                  f"{'bor' if page['has_next'] else 'yo‘q'}.")
        elif args.command == "corpus-withdraw":
            from backend import corpus
            removed = corpus.withdraw(args.document_id, config)
            print(f"Korpusdan chiqarildi va matni o‘chirildi: {removed['id']}.")
        else:
            password = hidden_password(f"Yangi akkaunt paroli (kamida {MIN_PASSWORD_CHARS} belgi): ")
            if password != hidden_password("Parolni takrorlang: "):
                raise ValueError("Parollar bir xil emas.")
            create_user(config, args.username, password, args.role)
            print("Akkaunt yaratildi.")
    except Exception as error:
        if diagnostic:
            diagnostic.record(error)
            print("Migratsiya tekshiruvi/bajarilishi muvaffaqiyatsiz.", file=sys.stderr)
            print(diagnostic.summary(), file=sys.stderr)
        elif isinstance(error, (ServiceError, ValueError, MigrationError, UsernameTakenError)):
            print(error.message if isinstance(error, ServiceError) else str(error), file=sys.stderr)
        else:
            raise
        sys.exit(1)
    finally:
        if diagnostic:
            driver_logger.setLevel(previous_log_level)


if __name__ == "__main__":
    main()
