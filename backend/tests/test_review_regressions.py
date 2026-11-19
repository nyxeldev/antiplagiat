"""Targeted auth review regressions; no existing database or external HTTP suite."""
import json
import secrets
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg

from backend import manage, persistence, reports
from backend.comparison import api
from backend.main import app
from backend.tests.fixtures import TEXT, multipart
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = {"status": "completed", "parameters": {"algorithm_version": "lexical-shingle-v1",
             "normalization_version": "uz-latin-v2"}, "document": {"name": "synthetic.txt"}}

# Real CLI process/exit status, with only terminal input replaced by synthetic stdin data.
# Passwords are never placed in subprocess arguments or source code.
CLI = """import json, sys
from unittest.mock import patch
from backend import manage
supplied = json.load(sys.stdin)
with patch.object(sys, 'argv', supplied['argv']), \
     patch.object(manage, 'prompt_database', return_value=supplied['database']), \
     patch.object(manage, 'hidden_password', return_value=supplied['password']):
    manage.main()
"""


def mock_connection(row=None):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.execute.return_value.fetchone.return_value = row
    return conn


class ContractTests(unittest.TestCase):
    def test_domain_exception_survives_database_wrapper_and_exits_context(self):
        conn = mock_connection()
        error = manage.UsernameTakenError("Bu login allaqachon band.")
        with patch.object(persistence.psycopg, "connect", return_value=conn):
            with self.assertRaises(manage.UsernameTakenError) as raised:
                with persistence.database({"dbname": "synthetic"}):
                    raise error
        self.assertIs(raised.exception, error)
        self.assertNotIsInstance(error, (ValueError, psycopg.Error))
        exited = conn.__exit__.call_args.args
        self.assertIs(exited[0], type(error))
        self.assertIs(exited[1], error)
        self.assertIsNotNone(exited[2])

    def test_save_insert_returns_snapshot_after_database_context(self):
        row = {"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc), "snapshot": SNAPSHOT}
        conn = mock_connection(row)
        with patch.object(persistence, "settings", return_value={"dbname": "synthetic"}), \
                patch.object(persistence.psycopg, "connect", return_value=conn), \
                patch.object(reports, "retry") as retry:
            result = reports.save(str(uuid.uuid4()), str(uuid.uuid4()), "a" * 64, SNAPSHOT)
        self.assertTrue(result["saved"])
        self.assertEqual(result["report_id"], str(row["id"]))
        conn.__exit__.assert_called_once_with(None, None, None)
        retry.assert_not_called()

    def test_save_insert_empty_preserves_retry_errors_and_success(self):
        saved = {"saved": True, "report_id": str(uuid.uuid4())}
        cases = [(saved, None),
                 (None, persistence.ServiceError("request_conflict", "sanitized", 409)),
                 (None, persistence.ServiceError("report_deleted", "sanitized", 410)),
                 (None, persistence.ServiceError("database_unavailable", "sanitized", 503))]
        for value, error in cases:
            conn = mock_connection()
            with self.subTest(code=error.code if error else "saved"), \
                    patch.object(persistence, "settings", return_value={"dbname": "synthetic"}), \
                    patch.object(persistence.psycopg, "connect", return_value=conn), \
                    patch.object(reports, "retry", return_value=value, side_effect=error):
                if error:
                    with self.assertRaises(persistence.ServiceError) as raised:
                        reports.save("owner", "key", "digest", SNAPSHOT)
                    self.assertIs(raised.exception, error)
                else:
                    self.assertIs(reports.save("owner", "key", "digest", SNAPSHOT), saved)
            conn.__exit__.assert_called_once_with(None, None, None)

    def test_save_database_error_remains_503_and_closes_context(self):
        conn = mock_connection()
        error = psycopg.OperationalError("private driver details")
        conn.execute.side_effect = error
        with patch.object(persistence, "settings", return_value={"dbname": "synthetic"}), \
                patch.object(persistence.psycopg, "connect", return_value=conn), \
                patch.object(reports, "retry") as retry:
            with self.assertRaises(persistence.ServiceError) as raised:
                reports.save("owner", "key", "digest", SNAPSHOT)
        self.assertEqual((raised.exception.status, raised.exception.code), (503, "database_unavailable"))
        self.assertNotIn("private", raised.exception.message)
        self.assertIs(conn.__exit__.call_args.args[1], error)
        retry.assert_not_called()


class ApiContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_and_retry_empty_api_returns_409_and_cleans_uploads(self):
        body, content_type = multipart([("document", "a.txt", TEXT.encode()), ("sources", "b.txt", TEXT.encode())])
        seen, connections, sent = [], [], []
        original = tempfile.TemporaryDirectory
        def temporary(**kwargs):
            directory = original(**kwargs)
            seen.append(directory.name)
            return directory
        def connect(**kwargs):
            conn = mock_connection()
            connections.append(conn)
            return conn
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "asgi": {"version": "3.0"}, "method": "POST", "scheme": "http",
                 "path": "/compare", "query_string": b"", "server": ("127.0.0.1", 8000),
                 "client": ("127.0.0.1", 10), "headers": [(b"content-type", content_type.encode()),
                 (b"idempotency-key", str(uuid.uuid4()).encode())]}
        with patch.object(api.auth, "require_user", return_value={"id": str(uuid.uuid4())}), \
                patch.object(api, "run_worker", return_value=SNAPSHOT), \
                patch.object(api.tempfile, "TemporaryDirectory", side_effect=temporary), \
                patch.object(persistence, "settings", return_value={"dbname": "synthetic"}), \
                patch.object(persistence.psycopg, "connect", side_effect=connect):
            await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        payload = json.loads(b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body"))
        self.assertEqual(start["status"], 409)
        self.assertEqual(payload["error"]["code"], "report_conflict")
        self.assertNotIn("saved", payload)
        self.assertTrue(seen and all(not Path(path).exists() for path in seen))
        self.assertFalse(api.gate.locked())
        self.assertEqual(len(connections), 3)  # preflight retry, INSERT, retry after conflict
        for conn in connections:
            conn.__exit__.assert_called_once_with(None, None, None)


class PostgresReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster = isolated_postgres()
        cls.admin, cls.runtime = cls.cluster.__enter__()
        cls.addClassCleanup(cls.cluster.__exit__, None, None, None)
        manage.migrate(cls.admin)

    def test_duplicate_username_cli_exit_and_unchanged_account(self):
        name = "cli-" + uuid.uuid4().hex[:12]
        password = secrets.token_urlsafe(24)
        def invoke(role):
            supplied = {"argv": ["manage", "create-user", name, "--role", role],
                        "database": self.admin, "password": password if role == "talaba" else secrets.token_urlsafe(24)}
            return subprocess.run([sys.executable, "-c", CLI], cwd=ROOT, input=json.dumps(supplied),
                                  capture_output=True, text=True, encoding="utf-8", timeout=15)
        first = invoke("talaba")
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stdout.strip(), "Akkaunt yaratildi.")
        with persistence.database(self.admin) as conn:
            before = conn.execute("SELECT * FROM antiplagiat.users WHERE username=%s", (name,)).fetchone()
        second = invoke("admin")
        self.assertEqual(second.returncode, 1)
        self.assertEqual(second.stderr.strip(), "Bu login allaqachon band.")
        self.assertEqual(second.stdout, "")
        self.assertNotIn(password, second.stderr)
        with persistence.database(self.admin) as conn:
            rows = conn.execute("SELECT * FROM antiplagiat.users WHERE username=%s", (name,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], before)  # Includes hash, role, id, enabled and created_at.

    def test_username_error_rolls_back_closes_and_other_unique_error_stays_503(self):
        name = "domain-" + uuid.uuid4().hex[:12]
        password = secrets.token_urlsafe(24)
        user_id = manage.create_user(self.admin, name, password)
        captured = []
        class TrackingConnection(psycopg.Connection):
            def rollback(self):
                self.did_rollback = True
                return super().rollback()
            def close(self):
                self.status_before_close = self.info.transaction_status
                return super().close()
        def connect(**kwargs):
            connection = TrackingConnection.connect(**kwargs)
            captured.append(connection)
            return connection
        with patch.object(persistence.psycopg, "connect", side_effect=connect):
            with self.assertRaises(manage.UsernameTakenError):
                manage.create_user(self.admin, name, secrets.token_urlsafe(24), role="admin")
        self.assertTrue(captured[0].did_rollback)
        self.assertEqual(captured[0].status_before_close, psycopg.pq.TransactionStatus.IDLE)
        self.assertTrue(captured[0].closed)
        # A different uniqueness constraint (users_pkey) must not become "login taken".
        with patch.object(manage.uuid, "uuid4", return_value=user_id):
            with self.assertRaises(persistence.ServiceError) as raised:
                manage.create_user(self.admin, "other-" + uuid.uuid4().hex[:12], password)
        self.assertEqual((raised.exception.status, raised.exception.code), (503, "database_unavailable"))

    def test_real_save_idempotent_retry_and_error_semantics(self):
        owner = manage.create_user(self.admin, "reports-" + uuid.uuid4().hex[:12], secrets.token_urlsafe(24))
        key, digest = str(uuid.uuid4()), "a" * 64
        with runtime_environment(self.runtime):
            saved = reports.save(owner, key, digest, SNAPSHOT)
            self.assertTrue(saved["saved"])
            self.assertEqual(reports.save(owner, key, digest, SNAPSHOT), saved)
            with self.assertRaises(persistence.ServiceError) as conflict:
                reports.save(owner, key, "b" * 64, SNAPSHOT)
            self.assertEqual((conflict.exception.status, conflict.exception.code), (409, "request_conflict"))
            reports.delete(owner, saved["report_id"])
            with self.assertRaises(persistence.ServiceError) as deleted:
                reports.save(owner, key, digest, SNAPSHOT)
            self.assertEqual((deleted.exception.status, deleted.exception.code), (410, "report_deleted"))
        with persistence.database(self.admin) as conn:
            row = conn.execute("SELECT count(*) AS n FROM antiplagiat.reports WHERE owner_id=%s AND request_key=%s", (owner, key)).fetchone()
        self.assertEqual(row["n"], 1)


if __name__ == "__main__":
    unittest.main()
