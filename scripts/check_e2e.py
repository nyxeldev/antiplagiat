"""Run synthetic real HTTP checks against owned loopback production servers.

Run from the project root with .venv/Scripts/python.exe scripts/check_e2e.py.
Build frontend first. Uses an owned disposable PostgreSQL cluster; no private files.
"""
import json
import http.cookiejar
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import secrets
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.tests.fixtures import TEXT, docx, pdf, multipart  # noqa: E402
from backend.comparison.matching import ARABIC_WARNING, INVISIBLE_WARNING  # noqa: E402
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment  # noqa: E402
from backend.manage import migrate, create_user, MigrationError  # noqa: E402
from backend.persistence import database, ServiceError  # noqa: E402
from backend import auth, reports  # noqa: E402

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ORIGIN = None


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, body=None, content_type=None, headers=None, method=None, opener=None):
    supplied = dict(headers or {})
    if content_type:
        supplied["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=supplied, method=method)
    try:
        response = (opener or OPENER).open(req, timeout=100)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            content = json.loads(content)
        return response.status, content


def wait_for(process, url):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Owned test server exited during startup")
        try:
            if request(url)[0] == 200:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("Owned test server did not start")


def checks(admin, runtime, password):
    global OPENER, ORIGIN
    if not (ROOT / "frontend/.next/BUILD_ID").exists():
        raise RuntimeError("Run npm.cmd run build in frontend first")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is unavailable")
    processes = []
    checks = 0
    db_checks = 0
    with tempfile.TemporaryDirectory(prefix="antiplagiat-e2e-") as scratch:
        scratch = Path(scratch)
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH"}}
        env.update(TEMP=str(scratch), TMP=str(scratch), PYTHONUTF8="1", NEXT_TELEMETRY_DISABLED="1")
        for key, suffix in (("host", "HOST"), ("port", "PORT"), ("dbname", "NAME"), ("user", "USER"), ("password", "PASSWORD")):
            env["ANTIPLAGIAT_DB_" + suffix] = runtime[key]
        backend_port = free_port()
        frontend_port = free_port()
        while frontend_port == backend_port:
            frontend_port = free_port()
        backend = f"http://127.0.0.1:{backend_port}"
        frontend = f"http://127.0.0.1:{frontend_port}"
        ORIGIN = frontend
        env["ANTIPLAGIAT_PUBLIC_ORIGIN"] = frontend
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--no-access-log"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            wait_for(processes[-1], backend + "/health")
            processes.append(subprocess.Popen([node, "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", str(frontend_port)], cwd=ROOT / "frontend", env={**env, "NODE_ENV": "production", "ANTIPLAGIAT_API_URL": backend}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            wait_for(processes[-1], frontend)
            status, html = request(frontend)
            assert status == 200 and "Islom akademiyasi — Antiplagiat" in html.decode()
            assert b'lang="uz"' in html
            checks += 1
            assert request(backend + "/health") == (200, {"status": "ok"})
            assert request(backend + "/ready") == (200, {"status": "ready"})
            checks += 2

            def new_client():
                jar = http.cookiejar.CookieJar()
                return urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)), jar

            client_a, jar_a = new_client()
            client_b, jar_b = new_client()
            anonymous, _ = new_client()
            common = {"X-Antiplagiat-Local": "1", "Origin": frontend}

            def call(path, client=None, method=None, data=None, expected=200, headers=None):
                nonlocal checks
                status, result = request(frontend + "/api" + path, json.dumps(data).encode() if data is not None else (b"" if method == "POST" else None),
                                         "application/json" if data is not None else None, {**common, **(headers or {})}, method, client)
                assert status == expected, (path, status, result.get("error"))
                checks += 1
                return result

            for path, method in [("/auth/me", "GET"), ("/reports", "GET"), ("/reports/" + str(uuid.uuid4()), "GET"),
                                 ("/reports/" + str(uuid.uuid4()), "DELETE"), ("/auth/logout", "POST")]:
                call(path, anonymous, method, expected=401)
            wrong = call("/auth/login", client_a, "POST", {"username": "test-a", "password": "wrong"}, 401)
            unknown = call("/auth/login", client_a, "POST", {"username": "unknown", "password": "wrong"}, 401)
            assert wrong == unknown
            call("/auth/login", client_a, "POST", {"username": "test-a", "password": password}, 403, {"Origin": "https://example.invalid"})
            call("/auth/login", client_a, "POST", {"username": "test-a", "password": password}, 403, {"Origin": ""})
            user_a = call("/auth/login", client_a, "POST", {"username": "test-a", "password": password})["user"]
            user_b = call("/auth/login", client_b, "POST", {"username": "test-b", "password": password})["user"]
            cookie_a = next(iter(jar_a))
            assert cookie_a.has_nonstandard_attr("HttpOnly") and cookie_a.get_nonstandard_attr("SameSite").lower() == "strict" and not cookie_a.secure
            with database(admin) as conn:
                session = conn.execute("SELECT token_hash FROM antiplagiat.sessions WHERE user_id=%s", (user_a["id"],)).fetchone()
                assert session["token_hash"] == auth.token_hash(cookie_a.value) and session["token_hash"] != cookie_a.value
            OPENER = client_a
            assert call("/reports", client_b)["items"] == []

            def upload(files, expected_status=200, code=None, percent=None, extra_headers=None):
                nonlocal checks
                body, kind = multipart(files)
                status, result = request(frontend + "/api/compare", body, kind, {**common, "Idempotency-Key": str(uuid.uuid4()), **(extra_headers or {})})
                assert status == expected_status, (status, result.get("error"))
                if code:
                    assert result["error"]["code"] == code, result["error"]
                    assert "coverage_percent" not in result
                if percent is not None:
                    assert result["saved"] and result["report_id"] and result["created_at"]
                    assert result["coverage_percent"] == percent, result["coverage_percent"]
                    for source in result["sources"]:
                        for match in source["matches"]:
                            for key, doc in [("document", result["document"]), ("source", source)]:
                                span = match[key]
                                assert doc["text"][span["start"]:span["end"]] == span["text"]
                assert not list(scratch.glob("antiplagiat-*")), "Temporary upload files leaked"
                checks += 1
                return result

            target = ("document", "target.txt", TEXT.encode())
            # A mutation with valid origin/header still requires an authenticated cookie.
            body, kind = multipart([target, ("sources", "s.txt", TEXT.encode())])
            assert request(frontend + "/api/compare", body, kind, {**common, "Idempotency-Key": str(uuid.uuid4())}, opener=anonymous)[0] == 401
            checks += 1
            for name, data in [("source.txt", TEXT.encode()), ("source.docx", docx()), ("source.pdf", pdf())]:
                upload([target, ("sources", name, data)], percent=100)
            upload([target, ("sources", "other.txt", b"osmon dengiz toglar qushlar yomgir daraxt")], percent=0)
            part = b"bir ikki uch tort besh olti"
            upload([("document", "partial.txt", part + b" yetti sakkiz toqqiz on"), ("sources", "one.txt", part), ("sources", "two.txt", part)], percent=60)
            upload([("document", "unicode.txt", "😀 O‘ZBEK  gʻoya\nmaʼno cafe\u0301 ＡＢＣ Straße".encode()), ("sources", "normal.txt", "o'zbek g'oya ma'no café abc strasse".encode())], percent=100)
            clean = "lotin matn uchun aniq manba nusxa"
            for invisible in ("\u200b", "\u00ad", "\u200c", "\ufeff", "\u200b\u00ad\u200c\ufeff"):
                changed = clean.replace("lotin", "lo" + invisible + "tin")
                result = upload([("document", "changed.txt", changed.encode()),
                                 ("sources", "clean.txt", clean.encode())], percent=100)
                assert result["document"]["text"] == changed
                assert result["sources"][0]["matches"][0]["method"] == "shingle"
                assert INVISIBLE_WARNING in result["limitations"]
                assert result["parameters"]["normalization_version"] == "uz-latin-v2"
            for text, warning in [("هذا نص عربي واضح للاختبار فقط", False),
                                  ("هَذا نص عربي واضح للاختبار فقط", True)]:
                result = upload([("document", "arabic.txt", text.encode()),
                                 ("sources", "same.txt", text.encode())], percent=100)
                assert (ARABIC_WARNING in result["limitations"]) == warning
                assert result["document"]["text"] == text
            unsafe = b"<script>alert('synthetic')</script> bir ikki uch tort besh"
            escaped = upload([("document", "safe.txt", unsafe), ("sources", "source.txt", unsafe)], percent=100)
            assert escaped["document"]["text"] == unsafe.decode()
            cases = [(b"", "empty.txt", "empty", 422), (b"broken", "broken.docx", "corrupt", 422),
                     (pdf(text="", scan=True), "scan.pdf", "no_text_layer", 422),
                     (pdf(encrypted=True), "locked.pdf", "encrypted", 422),
                     (b"invalid", "bad.exe", "unsupported", 415), (b"\xff", "bad.txt", "encoding", 422),
                     (b"x" * (10 * 1024 * 1024 + 1), "large.txt", "file_limit", 413)]
            for data, name, code, status in cases:
                upload([("document", name, data), ("sources", "source.txt", TEXT.encode())], status, code)
            upload([target], 400, "file_count")
            upload([target, ("sources", "source.txt", TEXT.encode())], 403, extra_headers={"Origin": "https://example.invalid"})
            body, kind = multipart([target, ("sources", "source.txt", TEXT.encode())])
            assert request(backend + "/compare", body, kind)[0] == 403
            checks += 1
            fixed_key = str(uuid.uuid4())
            saved = upload([target, ("sources", "s.txt", TEXT.encode())], percent=100, extra_headers={"Idempotency-Key": fixed_key})
            repeated = upload([target, ("sources", "s.txt", TEXT.encode())], percent=100, extra_headers={"Idempotency-Key": fixed_key})
            assert repeated == saved
            upload([target, ("sources", "s.txt", (TEXT + " changed").encode())], 409, "request_conflict", extra_headers={"Idempotency-Key": fixed_key})
            report_id = saved["report_id"]
            assert call("/reports/" + report_id, client_a) == saved
            assert report_id in [row["id"] for row in call("/reports", client_a)["items"]]
            assert call("/reports", client_b)["items"] == []
            call("/reports/" + report_id, client_b, expected=404)
            call("/reports/" + report_id, client_b, "DELETE", expected=404)
            call("/reports/" + report_id, client_a, "DELETE", expected=403, headers={"Origin": "https://example.invalid"})
            # Test immutable snapshot and minimum privileges using the actual runtime role.
            with runtime_environment(runtime):
                for statement in ("UPDATE antiplagiat.users SET role='admin'", "CREATE TABLE antiplagiat.forbidden(id int)",
                                  "DELETE FROM antiplagiat.reports", "SELECT * FROM antiplagiat.schema_migrations",
                                  "UPDATE antiplagiat.reports SET snapshot='{}'::jsonb"):
                    try:
                        with database() as conn:
                            conn.execute(statement)
                    except ServiceError:
                        db_checks += 1
                    else:
                        raise AssertionError("Runtime privilege/immutability regression")
                # More than one page, owner filtering independent of the UI.
                snapshot = {k: v for k, v in saved.items() if k not in {"saved", "report_id", "created_at"}}
                for _ in range(22):
                    reports.save(user_b["id"], str(uuid.uuid4()), "b" * 64, snapshot)
            page1 = call("/reports", client_b)
            page2 = call("/reports?page=2", client_b)
            assert len(page1["items"]) == 20 and page1["has_next"] and len(page2["items"]) == 2 and not page2["has_next"]
            assert not set(x["id"] for x in page1["items"]) & set(x["id"] for x in page2["items"])
            assert report_id not in [x["id"] for x in page1["items"] + page2["items"]]

            # Backend restart: cookie remains valid because sessions live in PostgreSQL.
            processes[0].terminate(); processes[0].wait(timeout=10)
            processes[0] = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--no-access-log"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            wait_for(processes[0], backend + "/health")
            assert call("/auth/me", client_a)["user"] == user_a
            assert call("/reports/" + report_id, client_a) == saved
            with database(admin) as conn:
                conn.execute("UPDATE antiplagiat.sessions SET expires_at=now()-interval '1 second' WHERE user_id=%s", (user_b["id"],))
            call("/auth/me", client_b, expected=401)
            call("/auth/login", client_b, "POST", {"username": "test-b", "password": password})

            # Actual save permission failure after worker: no false saved success, no leak.
            with database(admin) as conn:
                conn.execute("REVOKE INSERT ON antiplagiat.reports FROM antiplagiat_app")
            failure_key = str(uuid.uuid4())
            try:
                upload([target, ("sources", "s.txt", TEXT.encode())], 503, "database_unavailable", extra_headers={"Idempotency-Key": failure_key})
            finally:
                with database(admin) as conn:
                    conn.execute("GRANT INSERT ON antiplagiat.reports TO antiplagiat_app")
            upload([target, ("sources", "s.txt", TEXT.encode())], percent=100, extra_headers={"Idempotency-Key": failure_key})
            call("/reports/" + report_id, client_a, "DELETE")
            call("/reports/" + report_id, client_a, expected=404)
            upload([target, ("sources", "s.txt", TEXT.encode())], 410, "report_deleted", extra_headers={"Idempotency-Key": fixed_key})
            with database(admin) as conn:
                assert conn.execute("SELECT snapshot FROM antiplagiat.reports WHERE id=%s", (report_id,)).fetchone()["snapshot"] is None
            stale, stale_jar = new_client()
            import copy
            stale_jar.set_cookie(copy.copy(cookie_a))
            call("/auth/logout", client_a, "POST")
            call("/auth/me", stale, expected=401)
            call("/reports", client_a, expected=401)
            if "--browser" in sys.argv:
                from scripts.browser_checks import browser_checks
                browser_checks(frontend, password)
            for _ in range(auth.LOGIN_LIMIT + 1):
                status, result = request(frontend + "/api/auth/login", json.dumps({"username": "unknown", "password": "wrong"}).encode(), "application/json", common, "POST", anonymous)
            assert status == 429 and result["error"]["code"] == "login_limit"
            checks += 1
            print(f"PASS: {checks} real HTTP checks; production frontend -> FastAPI -> worker -> report.")
            print(f"PASS: {db_checks} separate PostgreSQL runtime privilege/immutability checks.")
            print("Three formats, exact/different/partial/duplicate/Unicode, invisible runs, Arabic warnings, policy version, offsets, errors, limits, local-only and cleanup verified.")
            print(f"Owned loopback ports: backend={backend_port}, frontend={frontend_port}")
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            print("Owned test servers stopped.")


def main():
    with isolated_postgres() as (admin, runtime):
        migrate(admin)
        migrate(admin)  # Checksums and grants are safely repeatable.
        try:
            migrate(runtime)
        except MigrationError:
            pass
        else:
            raise AssertionError("Runtime account must not migrate")
        with database(admin) as conn:
            original = conn.execute("SELECT version,checksum FROM antiplagiat.schema_migrations").fetchone()
            conn.execute("UPDATE antiplagiat.schema_migrations SET checksum='changed-by-owned-test' WHERE version=%s", (original["version"],))
        try:
            migrate(admin)
        except MigrationError:
            pass
        else:
            raise AssertionError("Changed applied migration must fail")
        finally:
            with database(admin) as conn:
                conn.execute("UPDATE antiplagiat.schema_migrations SET checksum=%s WHERE version=%s", (original["checksum"], original["version"]))
        print("PASS: PostgreSQL migration replay, checksum rejection and runtime migration denial.")
        password = secrets.token_urlsafe(24)
        create_user(admin, "test-a", password)
        create_user(admin, "test-b", password, role="admin")
        checks(admin, runtime, password)
    print("Owned disposable PostgreSQL cluster stopped and removed; existing database untouched.")


if __name__ == "__main__":
    main()
