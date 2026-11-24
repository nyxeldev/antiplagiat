"""accounts_api.py -- self-service password change (roles-phase1 Sect.24).
Runs against a real isolated cluster so the actual session/cookie machinery
(auth.require_user, rate_limit.enforce) is exercised exactly as the real app
would, not mocked away -- the same style as test_admin_api.py.
"""
import asyncio
import json
import secrets
import unittest
import uuid

from starlette.requests import Request

from backend import accounts_api, auth, manage
from backend.persistence import ServiceError
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment
from backend.tests.test_auth import request as bare_request

CLUSTER = {}


def setUpModule():
    CLUSTER["handle"] = isolated_postgres()
    CLUSTER["admin"], CLUSTER["runtime"] = CLUSTER["handle"].__enter__()
    manage.migrate(CLUSTER["admin"])


def tearDownModule():
    CLUSTER["handle"].__exit__(None, None, None)


class ChangePasswordTests(unittest.TestCase):
    def setUp(self):
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def unique(self, prefix):
        return f"{prefix}.{uuid.uuid4().hex[:8]}"

    def account(self, password):
        username = self.unique("pwchange")
        manage.create_user(CLUSTER["admin"], username, password, role="talaba")
        token, user = auth.login(username, password)
        return username, user["id"], token

    def request(self, token, body):
        payload = json.dumps(body).encode()
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}

        return Request({"type": "http", "method": "POST", "scheme": "http", "path": "/auth/change-password",
                        "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                        "headers": [(b"x-antiplagiat-local", b"1"), (b"content-type", b"application/json"),
                                    (b"origin", auth.public_origin().encode()),
                                    (b"cookie", f"{auth.COOKIE}={token}".encode())]}, receive)

    def change(self, token, old_password, new_password):
        return asyncio.run(accounts_api.change_password(self.request(token, {
            "old_password": old_password, "new_password": new_password})))

    def test_wrong_old_password_is_rejected(self):
        _, _, token = self.account(secrets.token_urlsafe(24))
        with self.assertRaises(ServiceError) as raised:
            self.change(token, "totally-wrong-password", secrets.token_urlsafe(24))
        self.assertEqual(raised.exception.status, 401)

    def test_weak_new_password_is_rejected(self):
        old_password = secrets.token_urlsafe(24)
        _, _, token = self.account(old_password)
        with self.assertRaises(ServiceError) as raised:
            self.change(token, old_password, "1" * manage.MIN_PASSWORD_CHARS)
        self.assertEqual(raised.exception.status, 400)

    def test_too_short_new_password_is_rejected(self):
        old_password = secrets.token_urlsafe(24)
        _, _, token = self.account(old_password)
        with self.assertRaises(ServiceError) as raised:
            self.change(token, old_password, "x" * (manage.MIN_PASSWORD_CHARS - 1))
        self.assertEqual(raised.exception.status, 400)

    def test_successful_change_logs_in_with_new_password_only(self):
        old_password, new_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        username, _, token = self.account(old_password)
        self.change(token, old_password, new_password)
        new_token, _ = auth.login(username, new_password)
        self.assertTrue(new_token)
        with self.assertRaises(ServiceError) as raised:
            auth.login(username, old_password)
        self.assertEqual(raised.exception.status, 401)

    def test_successful_change_invalidates_every_existing_session(self):
        old_password, new_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        username, _, token = self.account(old_password)
        other_token, _ = auth.login(username, old_password)  # a second, concurrent session
        self.change(token, old_password, new_password)
        for dead_token in (token, other_token):
            with self.subTest(token=dead_token), self.assertRaises(ServiceError) as raised:
                auth.require_user(bare_request(cookie=dead_token))
            self.assertEqual(raised.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
