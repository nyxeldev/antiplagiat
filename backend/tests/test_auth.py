import secrets
import json
import getpass
import warnings
import unittest
from unittest.mock import MagicMock, patch

import psycopg
from starlette.requests import Request

from backend import auth, reports
from backend import accounts_api
from backend.manage import hidden_password
from backend.persistence import ServiceError, database


def request(method="GET", headers=None, cookie=None):
    supplied = {"x-antiplagiat-local": "1", **(headers or {})}
    if cookie:
        supplied["cookie"] = f"{auth.COOKIE}={cookie}"
    return Request({"type": "http", "method": method, "scheme": "http", "path": "/",
                    "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                    "headers": [(k.encode(), v.encode()) for k, v in supplied.items()]})


class AuthTests(unittest.TestCase):
    def test_cli_password_uses_hidden_terminal_input(self):
        with patch("backend.manage.getpass.getpass", return_value="synthetic-secret") as read:
            self.assertEqual(hidden_password("Parol: "), "synthetic-secret")
            read.assert_called_once_with("Parol: ")

    def test_cli_refuses_echo_fallback(self):
        def fallback(prompt):
            warnings.warn("echo unavailable", getpass.GetPassWarning)
            raise AssertionError("Unhidden input must never be read")
        with patch("backend.manage.getpass.getpass", side_effect=fallback), self.assertRaises(ValueError) as raised:
            hidden_password("Parol: ")
        self.assertNotIn("synthetic-secret", str(raised.exception))

    def test_argon2_real_hash_verify(self):
        password = secrets.token_urlsafe(20)
        first, second = auth.password_hash(password), auth.password_hash(password)
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertNotEqual(first, second)
        self.assertTrue(auth.HASHER.verify(first, password))
        with self.assertRaises(auth.VerificationError):
            auth.HASHER.verify(first, "wrong")

    def test_origin_mutations_and_local_only(self):
        with patch.dict("os.environ", {"ANTIPLAGIAT_PUBLIC_ORIGIN": "http://127.0.0.1:3000"}):
            auth.guard(request("POST", {"origin": "http://127.0.0.1:3000"}))
            for headers in ({}, {"origin": "https://evil.invalid"}, {"origin": "null"},
                            {"origin": "http://127.0.0.1:3000", "x-antiplagiat-local": "0"},
                            {"origin": "http://127.0.0.1:3000", "sec-fetch-site": "cross-site"}):
                with self.subTest(headers=headers), self.assertRaises(ServiceError) as raised:
                    auth.guard(request("DELETE", headers))
                self.assertEqual(raised.exception.status, 403)

    def test_anonymous_and_expired_session(self):
        with self.assertRaises(ServiceError) as raised:
            auth.require_user(request())
        self.assertEqual(raised.exception.status, 401)
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        with patch.object(auth, "database") as db:
            db.return_value.__enter__.return_value = conn
            with self.assertRaises(ServiceError) as raised:
                auth.require_user(request(cookie=secrets.token_urlsafe(32)))
            self.assertEqual(raised.exception.status, 401)
            self.assertIn("expires_at>now()", conn.execute.call_args.args[0])

    def test_limiter_is_bounded_and_expires(self):
        limiter = auth.LoginLimiter()
        with patch.object(auth.time, "monotonic", return_value=10):
            for _ in range(auth.LOGIN_LIMIT):
                limiter.check("127.0.0.1")
            with self.assertRaises(ServiceError) as raised:
                limiter.check("127.0.0.1")
            self.assertEqual(raised.exception.status, 429)
        with patch.object(auth.time, "monotonic", return_value=10 + auth.LOGIN_WINDOW + 1):
            limiter.check("127.0.0.1")

    def test_database_error_is_sanitized_and_rollback_closes(self):
        config = dict(host="127.0.0.1", port="5432", dbname="test", user="runtime", password="synthetic-secret")
        conn = MagicMock()
        conn.execute.side_effect = psycopg.OperationalError("synthetic-secret private SQL error")
        with patch("backend.persistence.psycopg.connect", return_value=conn):
            with self.assertRaises(ServiceError) as raised:
                with database(config) as opened:
                    # context-managed connection's entered value
                    opened.execute.side_effect = conn.execute.side_effect
                    opened.execute("SELECT 1")
            self.assertEqual(raised.exception.status, 503)
            self.assertNotIn("synthetic-secret", raised.exception.message)
            conn.__exit__.assert_called_once()

    def test_owner_predicate_for_report_get_delete_list(self):
        conn = MagicMock(); conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.fetchall.return_value = []
        with patch.object(reports, "database") as db:
            db.return_value.__enter__.return_value = conn
            for action in (reports.get, reports.delete):
                with self.assertRaises(ServiceError) as raised:
                    action("owner-a", "report-b")
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(conn.execute.call_args.args[1], ("owner-a", "report-b"))
                self.assertIn("owner_id=%s", conn.execute.call_args.args[0])
            self.assertEqual(reports.history("owner-a", 2)["items"], [])
            self.assertEqual(conn.execute.call_args.args[1], ("owner-a", 20))


class CookieTests(unittest.IsolatedAsyncioTestCase):
    async def test_https_secure_cookie_and_no_token_in_body(self):
        token = secrets.token_urlsafe(32)
        user = {"id": "test", "username": "test-user", "role": "user"}
        body = json.dumps({"username": "test-user", "password": "synthetic-password"}).encode()
        req = request("POST", {"origin": "https://localhost:3000"})
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        req._receive = receive
        with patch.dict("os.environ", {"ANTIPLAGIAT_PUBLIC_ORIGIN": "https://localhost:3000"}), \
                patch.object(auth, "login", return_value=(token, user)), \
                patch.object(auth.limiter, "check"):
            result = await accounts_api.login(req)
        self.assertEqual(result.status_code, 200)
        cookie = result.headers["set-cookie"]
        for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertNotIn(token, result.body.decode())
        self.assertNotIn("synthetic-password", result.body.decode())


if __name__ == "__main__":
    unittest.main()
