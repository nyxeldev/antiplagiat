"""Owned disposable PostgreSQL cluster. Never connects to the user's database."""
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from psycopg import sql

from backend.persistence import database


@contextmanager
def isolated_postgres():
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("PostgreSQL initdb/pg_ctl kerak. Bu test mock yoki SQLitega o‘tmaydi.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Short owned path also avoids Windows socket/path limits.
    scratch = Path(tempfile.mkdtemp(prefix="antiplagiat-pg-"))
    data = scratch / "data"
    password = secrets.token_urlsafe(32)
    runtime_password = secrets.token_urlsafe(32)
    pwfile = scratch / "password"
    pwfile.write_text(password, encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    def command(args):
        return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30, creationflags=flags).returncode
    started = False
    try:
        if command([initdb, "-D", str(data), "-U", "migration_account", "--pwfile", str(pwfile), "-A", "scram-sha-256", "--encoding=UTF8", "--locale=C"]):
            raise RuntimeError("Owned PostgreSQL cluster initialization failed")
        pwfile.unlink()
        started = True  # stop attempted even if pg_ctl startup reports an error
        if command([pg_ctl, "-D", str(data), "-l", str(scratch / "server.log"), "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"]):
            raise RuntimeError("Owned PostgreSQL server failed to start")
        admin = dict(host="127.0.0.1", port=str(port), dbname="postgres", user="migration_account", password=password)
        runtime = {**admin, "user": "antiplagiat_app", "password": runtime_password}
        with database(admin) as conn:
            conn.execute(sql.SQL("CREATE ROLE antiplagiat_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Literal(runtime_password)))
            conn.execute("REVOKE ALL ON DATABASE postgres FROM PUBLIC")
            conn.execute("GRANT CONNECT ON DATABASE postgres TO antiplagiat_app")
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        yield admin, runtime
    finally:
        if started and command([pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"]):
            raise RuntimeError("Owned PostgreSQL could not stop; scratch directory retained")
        # Only this freshly created directory; never remove a caller-supplied path.
        if scratch.resolve().parent == Path(tempfile.gettempdir()).resolve() and scratch.name.startswith("antiplagiat-pg-"):
            shutil.rmtree(scratch)


@contextmanager
def runtime_environment(config):
    keys = {"ANTIPLAGIAT_DB_" + suffix: config[key] for key, suffix in
            (("host", "HOST"), ("port", "PORT"), ("dbname", "NAME"), ("user", "USER"), ("password", "PASSWORD"))}
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(keys)
    try:
        yield keys
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
