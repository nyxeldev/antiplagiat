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
    log = scratch / "server.log"
    cmd_output = scratch / "cmd-output.log"
    def command(args):
        # Captured to a real file, not PIPE: pg_ctl start's own child
        # (postgres, left running) can inherit a pipe's write handle on
        # Windows, which then never reports EOF and makes a later
        # communicate()/run() wait forever even past its own timeout. A
        # file has no such reader to block, since wait() here only waits
        # on the directly spawned process (pg_ctl), not its descendants.
        with cmd_output.open("wb") as handle:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=handle,
                                    stderr=subprocess.STDOUT, timeout=30, creationflags=flags)
        return result.returncode, cmd_output.read_text(encoding="utf-8", errors="replace")
    def failure(message, output):
        # pg_ctl's own stdout/stderr is usually just "waiting for server to
        # start.... stopped waiting"; the actual reason postgres refused to
        # start is in the server log pg_ctl -l writes, which the `finally`
        # below unconditionally deletes with the rest of the scratch
        # directory -- so it must be read into the exception here, before
        # that happens, or it is lost.
        detail = (output or "").strip()
        if log.exists():
            detail = (detail + "\n--- server.log ---\n" + log.read_text(encoding="utf-8", errors="replace")).strip()
        return RuntimeError(f"{message}:\n{detail}" if detail else message)
    started = False
    try:
        code, output = command([initdb, "-D", str(data), "-U", "migration_account", "--pwfile", str(pwfile), "-A", "scram-sha-256", "--encoding=UTF8", "--locale=C"])
        if code:
            raise failure("Owned PostgreSQL cluster initialization failed", output)
        pwfile.unlink()
        started = True  # stop attempted even if pg_ctl startup reports an error
        # unix_socket_directories="" -- this fixture only ever connects over
        # TCP (127.0.0.1); the compiled-in default directory (e.g. Debian's
        # /var/run/postgresql) can be owned by a system "postgres" account
        # that an unprivileged CI runner user cannot write a socket lock
        # file into, which fails startup with nothing about TCP at fault.
        code, output = command([pg_ctl, "-D", str(data), "-l", str(log),
                                "-o", f"-h 127.0.0.1 -p {port} -c unix_socket_directories=", "-w", "start"])
        if code:
            raise failure("Owned PostgreSQL server failed to start", output)
        admin = dict(host="127.0.0.1", port=str(port), dbname="postgres", user="migration_account", password=password)
        runtime = {**admin, "user": "antiplagiat_app", "password": runtime_password}
        with database(admin) as conn:
            conn.execute(sql.SQL("CREATE ROLE antiplagiat_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Literal(runtime_password)))
            conn.execute("REVOKE ALL ON DATABASE postgres FROM PUBLIC")
            conn.execute("GRANT CONNECT ON DATABASE postgres TO antiplagiat_app")
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        yield admin, runtime
    finally:
        if started:
            code, output = command([pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"])
            if code:
                raise failure("Owned PostgreSQL could not stop; scratch directory retained", output)
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
