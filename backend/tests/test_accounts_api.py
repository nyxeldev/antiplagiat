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
from backend.tests.fixtures import multipart
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


class FullNameTests(unittest.TestCase):
    """POST /auth/full-name -- roles-phase1 Sect.25."""

    def setUp(self):
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def account(self):
        username, password = f"fullname.{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(24)
        manage.create_user(CLUSTER["admin"], username, password, role="talaba")
        token, user = auth.login(username, password)
        return user["id"], token

    def request(self, token, body):
        payload = json.dumps(body).encode()
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}

        return Request({"type": "http", "method": "POST", "scheme": "http", "path": "/auth/full-name",
                        "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                        "headers": [(b"x-antiplagiat-local", b"1"), (b"content-type", b"application/json"),
                                    (b"origin", auth.public_origin().encode()),
                                    (b"cookie", f"{auth.COOKIE}={token}".encode())]}, receive)

    def set_name(self, token, full_name):
        return asyncio.run(accounts_api.set_full_name(self.request(token, {"full_name": full_name})))

    def test_setting_full_name_is_reflected_in_profile(self):
        user_id, token = self.account()
        self.set_name(token, "Aziz Aliyev")
        self.assertEqual(auth.get_profile(user_id)["full_name"], "Aziz Aliyev")

    def test_blank_full_name_clears_it(self):
        user_id, token = self.account()
        self.set_name(token, "Aziz Aliyev")
        self.set_name(token, "   ")
        self.assertIsNone(auth.get_profile(user_id)["full_name"])

    def test_too_long_full_name_is_rejected(self):
        _, token = self.account()
        with self.assertRaises(ServiceError) as raised:
            self.set_name(token, "a" * 121)
        self.assertEqual(raised.exception.status, 400)


class UsernameChangeTests(unittest.TestCase):
    """POST /auth/username -- roles-phase1 Sect.25."""

    def setUp(self):
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def account(self):
        username, password = f"uname.{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(24)
        manage.create_user(CLUSTER["admin"], username, password, role="talaba")
        token, user = auth.login(username, password)
        return user["id"], token

    def request(self, token, body):
        payload = json.dumps(body).encode()
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}

        return Request({"type": "http", "method": "POST", "scheme": "http", "path": "/auth/username",
                        "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                        "headers": [(b"x-antiplagiat-local", b"1"), (b"content-type", b"application/json"),
                                    (b"origin", auth.public_origin().encode()),
                                    (b"cookie", f"{auth.COOKIE}={token}".encode())]}, receive)

    def change(self, token, new_username):
        return asyncio.run(accounts_api.set_username(self.request(token, {"username": new_username})))

    def test_successful_change_is_reflected_in_profile(self):
        user_id, token = self.account()
        new_username = f"renamed.{uuid.uuid4().hex[:8]}"
        self.change(token, new_username)
        self.assertEqual(auth.get_profile(user_id)["username"], new_username)

    def test_taken_username_is_rejected(self):
        _, token = self.account()
        other_username, other_password = f"uname.{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(24)
        manage.create_user(CLUSTER["admin"], other_username, other_password, role="talaba")
        with self.assertRaises(ServiceError) as raised:
            self.change(token, other_username)
        self.assertEqual(raised.exception.status, 409)

    def test_invalid_username_shape_is_rejected(self):
        _, token = self.account()
        with self.assertRaises(ServiceError) as raised:
            self.change(token, "AB")  # too short, and uppercase is outside valid_username()'s shape
        self.assertEqual(raised.exception.status, 400)


class AvatarTests(unittest.TestCase):
    """POST/DELETE /auth/avatar, GET /auth/avatar/{user_id} -- roles-phase1
    Sect.25. No Pillow (see docs/decisions.md): only a magic-byte sniff, so
    these fixtures only ever need a real signature, never a decodable image.
    """

    PNG_HEADER = b"\x89PNG\r\n\x1a\n"

    def setUp(self):
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def account(self):
        username, password = f"avatar.{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(24)
        manage.create_user(CLUSTER["admin"], username, password, role="talaba")
        token, user = auth.login(username, password)
        return user["id"], token

    def upload(self, token, content):
        body, kind = multipart([("file", "pic.png", content)])
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope = {"type": "http", "method": "POST", "scheme": "http", "path": "/auth/avatar",
                 "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                 "headers": [(b"x-antiplagiat-local", b"1"), (b"content-type", kind.encode()),
                             (b"content-length", str(len(body)).encode()),
                             (b"origin", auth.public_origin().encode()),
                             (b"cookie", f"{auth.COOKIE}={token}".encode())]}
        return asyncio.run(accounts_api.upload_avatar(Request(scope, receive)))

    def test_uploading_a_valid_png_sets_has_avatar(self):
        user_id, token = self.account()
        self.upload(token, self.PNG_HEADER + b"synthetic-test-only")
        self.assertTrue(auth.get_profile(user_id)["has_avatar"])
        raw, mime = auth.get_avatar(user_id)
        self.assertEqual(mime, "image/png")
        self.assertTrue(raw.startswith(self.PNG_HEADER))

    def test_non_image_bytes_are_rejected(self):
        _, token = self.account()
        with self.assertRaises(ServiceError) as raised:
            self.upload(token, b"this is not an image, just plain text")
        self.assertEqual(raised.exception.status, 415)

    def test_oversized_avatar_is_rejected(self):
        _, token = self.account()
        oversized = self.PNG_HEADER + b"0" * auth.MAX_AVATAR_BYTES
        with self.assertRaises(ServiceError) as raised:
            self.upload(token, oversized)
        self.assertEqual(raised.exception.status, 413)

    def test_deleting_avatar_clears_has_avatar(self):
        user_id, token = self.account()
        self.upload(token, self.PNG_HEADER + b"synthetic-test-only")
        asyncio.run(accounts_api.delete_avatar(bare_request(method="DELETE",
            headers={"origin": auth.public_origin()}, cookie=token)))
        self.assertFalse(auth.get_profile(user_id)["has_avatar"])

    def test_missing_avatar_and_missing_account_404_identically(self):
        """No-existence-leak: a real account with no avatar and a wholly
        made-up id must be indistinguishable to the caller."""
        user_id, _ = self.account()
        with self.assertRaises(ServiceError) as present:
            auth.get_avatar(user_id)
        with self.assertRaises(ServiceError) as absent:
            auth.get_avatar(str(uuid.uuid4()))
        self.assertEqual(present.exception.status, 404)
        self.assertEqual(present.exception.status, absent.exception.status)
        self.assertEqual(present.exception.message, absent.exception.message)


class SessionListTests(unittest.TestCase):
    """GET /auth/sessions, POST /auth/sessions/revoke-others -- roles-phase1
    Sect.25, tested at the auth.py layer directly (the endpoints themselves
    are thin pass-throughs already covered by PermissionMatrixTests)."""

    def setUp(self):
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def account(self):
        username, password = f"sessions.{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(24)
        manage.create_user(CLUSTER["admin"], username, password, role="talaba")
        return username, password

    def test_listing_shows_every_active_session_and_marks_the_current_one(self):
        username, password = self.account()
        token_a, user = auth.login(username, password)
        token_b, _ = auth.login(username, password)
        from_a = auth.list_sessions(user["id"], token_a)["items"]
        from_b = auth.list_sessions(user["id"], token_b)["items"]
        self.assertEqual(len(from_a), 2)
        self.assertEqual(sum(1 for item in from_a if item["is_current"]), 1)
        # Each caller's OWN token is the one marked current, not the other's.
        self.assertNotEqual([i["is_current"] for i in from_a], [i["is_current"] for i in from_b])

    def test_revoke_others_keeps_the_calling_session_alive(self):
        username, password = self.account()
        token_a, user = auth.login(username, password)
        token_b, _ = auth.login(username, password)
        auth.revoke_other_sessions(user["id"], token_a)
        self.assertEqual(len(auth.list_sessions(user["id"], token_a)["items"]), 1)
        with self.assertRaises(ServiceError) as raised:
            auth.require_user(bare_request(cookie=token_b))
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(auth.require_user(bare_request(cookie=token_a))["id"], user["id"])


if __name__ == "__main__":
    unittest.main()
