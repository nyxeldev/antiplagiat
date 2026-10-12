"""python -m backend.manage migrate / create-user.

All database/account passwords are read with getpass in a local terminal.
Never load .env, accept passwords as arguments or print raw database errors.
"""
import argparse
import getpass
import hashlib
import os
import sys
import uuid
import warnings
from pathlib import Path

from psycopg import sql

from backend.persistence import ServiceError, database


class MigrationError(Exception):
    """Safe actionable migration errors, separate from raw driver errors."""


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


def migrate(config, runtime_role="antiplagiat_app"):
    with database(config) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(71920261013)")
        principal = conn.execute("SELECT current_user AS name").fetchone()["name"]
        if principal == runtime_role:
            raise MigrationError("Migratsiya runtime hisobidan alohida vakolatli hisobni talab qiladi.")
        role = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s", (runtime_role,)).fetchone()
        owner = conn.execute("SELECT pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname=current_database()").fetchone()
        if not role or role["rolsuper"] or owner["owner"] == runtime_role:
            raise MigrationError("Runtime hisobi mavjud, superuser bo‘lmagan va DB egasi bo‘lmagan hisob bo‘lishi kerak.")
        conn.execute("CREATE SCHEMA IF NOT EXISTS antiplagiat")
        conn.execute("CREATE TABLE IF NOT EXISTS antiplagiat.schema_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        files = sorted((Path(__file__).parent / "migrations").glob("*.sql"))
        known = {p.stem for p in files}
        applied = {row["version"]: row["checksum"] for row in conn.execute("SELECT version, checksum FROM antiplagiat.schema_migrations")}
        if applied.keys() - known:
            raise MigrationError("Bazada ushbu kod tanimaydigan migratsiya bor.")
        for path in files:
            content = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            if path.stem in applied:
                if applied[path.stem] != checksum:
                    raise MigrationError("Bajarilgan migratsiya o‘zgargan; yangi versiya yarating.")
                continue
            conn.execute(content)
            conn.execute("INSERT INTO antiplagiat.schema_migrations(version, checksum) VALUES (%s,%s)", (path.stem, checksum))
        ident = sql.Identifier(runtime_role)
        conn.execute(sql.SQL("REVOKE ALL ON SCHEMA antiplagiat FROM PUBLIC, {}").format(ident))
        conn.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA antiplagiat FROM PUBLIC, {} ").format(ident))
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA antiplagiat TO {}").format(ident))
        conn.execute(sql.SQL("GRANT SELECT ON antiplagiat.users TO {}").format(ident))
        conn.execute(sql.SQL("GRANT SELECT, INSERT, DELETE ON antiplagiat.sessions TO {}").format(ident))
        conn.execute(sql.SQL("GRANT SELECT, INSERT ON antiplagiat.reports TO {}").format(ident))
        conn.execute(sql.SQL("GRANT UPDATE(snapshot, deleted_at) ON antiplagiat.reports TO {}").format(ident))
        conn.execute("REVOKE ALL ON FUNCTION antiplagiat.guard_report() FROM PUBLIC")
    return len(files)


def create_user(config, username, password, role="user"):
    from backend.auth import password_hash, valid_username
    if not valid_username(username) or not 12 <= len(password) <= 256:
        raise ValueError("Login: 3–64 kichik lotin harfi/son/_.-; parol: 12–256 belgi.")
    user_id = uuid.uuid4()
    hashed = password_hash(password)
    with database(config) as conn:
        conn.execute("INSERT INTO antiplagiat.users(id,username,password_hash,role) VALUES (%s,%s,%s,%s)",
                     (user_id, username, hashed, role))
    return user_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    migration = sub.add_parser("migrate")
    migration.add_argument("--runtime-role", default="antiplagiat_app")
    account = sub.add_parser("create-user")
    account.add_argument("username")
    account.add_argument("--role", choices=["user", "reviewer", "corpus_manager", "admin"], default="user")
    args = parser.parse_args()
    try:
        config = prompt_database()
        if args.command == "migrate":
            count = migrate(config, args.runtime_role)
            print(f"Migratsiyalar tayyor: {count}; runtime huquqlari cheklangan.")
        else:
            password = hidden_password("Yangi akkaunt paroli (kamida 12 belgi): ")
            if password != hidden_password("Parolni takrorlang: "):
                raise ValueError("Parollar bir xil emas.")
            create_user(config, args.username, password, args.role)
            print("Akkaunt yaratildi.")
    except (ServiceError, ValueError, MigrationError) as error:
        print(error.message if isinstance(error, ServiceError) else str(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
