"""Admin panel -- roles-phase1 3-bosqich (docs/decisions.md Sect.20). These
tests call backend/admin_api.py's endpoints directly, with config=None always
(exactly like the real app), inside runtime_environment() -- proving the new
antiplagiat_app grants (not just the privileged migration account) actually
let these actions succeed.
"""
import asyncio
import json
import secrets
import unittest
import uuid
from unittest.mock import patch

from starlette.requests import Request

from backend import admin_api, auth, manage
from backend.persistence import ServiceError
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment

CLUSTER = {}


def setUpModule():
    """One owned disposable cluster for the whole module."""
    CLUSTER["handle"] = isolated_postgres()
    CLUSTER["admin"], CLUSTER["runtime"] = CLUSTER["handle"].__enter__()
    manage.migrate(CLUSTER["admin"])
    # A real row, not a bare uuid4 -- rate_limit_counters.user_id has a FK
    # onto users(id), so admin_api's rate_limit.enforce(admin["id"], ...)
    # needs an admin account that actually exists.
    CLUSTER["admin_id"] = manage.create_user(CLUSTER["admin"], "admin.panel.admin",
                                             secrets.token_urlsafe(24), role="admin")


def tearDownModule():
    CLUSTER["handle"].__exit__(None, None, None)


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.admin_user = {"id": str(CLUSTER["admin_id"]), "role": "admin"}
        self.patcher = patch.object(admin_api.auth, "require_admin", return_value=self.admin_user)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.runtime = runtime_environment(CLUSTER["runtime"])
        self.runtime.__enter__()
        self.addCleanup(self.runtime.__exit__, None, None, None)

    def unique(self, prefix):
        return f"{prefix}.{uuid.uuid4().hex[:8]}"

    def scope(self, method, path):
        return {"type": "http", "method": method, "scheme": "http", "path": path,
                "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                "headers": [(b"x-antiplagiat-local", b"1"), (b"content-type", b"application/json")]}

    def get(self, path):
        return Request(self.scope("GET", path))

    def post(self, path, body):
        payload = json.dumps(body).encode()
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}

        return Request(self.scope("POST", path), receive)

    def payload(self, response):
        return json.loads(bytes(response.body))

    def create_account(self, username, password, role):
        return asyncio.run(admin_api.create_account(self.post("/admin/users", {
            "username": username, "password": password, "role": role})))

    def set_role(self, user_id, role):
        return asyncio.run(admin_api.set_role(self.post(f"/admin/users/{user_id}/role", {"role": role}), user_id))

    def set_kafedra(self, user_id, qisqa_kodi):
        return asyncio.run(admin_api.set_kafedra(
            self.post(f"/admin/users/{user_id}/kafedra", {"qisqa_kodi": qisqa_kodi}), user_id))

    def set_enabled(self, user_id, enabled):
        return asyncio.run(admin_api.set_enabled(
            self.post(f"/admin/users/{user_id}/enabled", {"enabled": enabled}), user_id))

    def create_kafedra(self, nomi, qisqa_kodi):
        return asyncio.run(admin_api.create_kafedra(self.post("/admin/kafedra", {
            "nomi": nomi, "qisqa_kodi": qisqa_kodi})))

    # --- users ---

    def test_search_returns_matching_accounts_without_password_hash(self):
        username = self.unique("search-target")
        self.create_account(username, secrets.token_urlsafe(24), "talaba")
        response = admin_api.search_users(self.get("/admin/users"), q=username)
        items = self.payload(response)["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["username"], username)
        self.assertNotIn("password_hash", items[0])

    def test_create_account_rejects_super_admin_role(self):
        with self.assertRaises(ServiceError) as raised:
            self.create_account(self.unique("wannabe"), secrets.token_urlsafe(24), "super_admin")
        self.assertEqual(raised.exception.status, 400)

    def test_create_account_rejects_weak_password(self):
        with self.assertRaises(ServiceError) as raised:
            self.create_account(self.unique("weakpass"), "1" * manage.MIN_PASSWORD_CHARS, "talaba")
        self.assertEqual(raised.exception.status, 400)

    def test_duplicate_username_is_a_clean_409_not_a_500(self):
        username = self.unique("dupe")
        self.create_account(username, secrets.token_urlsafe(24), "talaba")
        with self.assertRaises(ServiceError) as raised:
            self.create_account(username, secrets.token_urlsafe(24), "talaba")
        self.assertEqual(raised.exception.status, 409)

    def test_created_account_can_actually_log_in(self):
        username, password = self.unique("login-check"), secrets.token_urlsafe(24)
        self.create_account(username, password, "talaba")
        token, user = auth.login(username, password)
        self.assertTrue(token)
        self.assertEqual(user["username"], username)

    def test_role_assignment_rejects_super_admin_and_unknown_roles(self):
        created = self.payload(self.create_account(self.unique("roletarget"), secrets.token_urlsafe(24), "talaba"))
        for bad_role in ("super_admin", "bogus"):
            with self.subTest(role=bad_role), self.assertRaises(ServiceError) as raised:
                self.set_role(created["id"], bad_role)
            self.assertEqual(raised.exception.status, 400)

    def test_role_assignment_updates_an_existing_account(self):
        created = self.payload(self.create_account(self.unique("promote"), secrets.token_urlsafe(24), "talaba"))
        updated = self.payload(self.set_role(created["id"], "ustoz"))
        self.assertEqual(updated["role"], "ustoz")

    def test_disabling_an_account_blocks_its_next_login(self):
        username, password = self.unique("disable-target"), secrets.token_urlsafe(24)
        created = self.payload(self.create_account(username, password, "talaba"))
        auth.login(username, password)  # proves the account works before disabling it
        disabled = self.payload(self.set_enabled(created["id"], False))
        self.assertFalse(disabled["enabled"])
        with self.assertRaises(ServiceError) as raised:
            auth.login(username, password)
        self.assertEqual(raised.exception.status, 401)

    def test_re_enabling_restores_login(self):
        username, password = self.unique("re-enable-target"), secrets.token_urlsafe(24)
        created = self.payload(self.create_account(username, password, "talaba"))
        self.set_enabled(created["id"], False)
        enabled = self.payload(self.set_enabled(created["id"], True))
        self.assertTrue(enabled["enabled"])
        token, _ = auth.login(username, password)
        self.assertTrue(token)

    def test_admin_cannot_disable_their_own_account(self):
        with self.assertRaises(ServiceError) as raised:
            self.set_enabled(CLUSTER["admin_id"], False)
        self.assertEqual(raised.exception.status, 400)

    def test_set_enabled_rejects_unknown_user(self):
        with self.assertRaises(ServiceError) as raised:
            self.set_enabled(uuid.uuid4(), False)
        self.assertEqual(raised.exception.status, 404)

    # --- kafedra ---

    def test_kafedra_create_and_list_roundtrip(self):
        nomi, qisqa_kodi = self.unique("Yangi Kafedra"), self.unique("yk")
        created = self.payload(self.create_kafedra(nomi, qisqa_kodi))
        listed = self.payload(admin_api.list_kafedra(self.get("/admin/kafedra")))["items"]
        self.assertIn(created["id"], [row["id"] for row in listed])
        self.assertIn(qisqa_kodi, [row["qisqa_kodi"] for row in listed])

    def test_kafedra_create_rejects_duplicate_qisqa_kodi(self):
        qisqa_kodi = self.unique("dup-kafedra")
        self.create_kafedra(self.unique("Kafedra Bir"), qisqa_kodi)
        with self.assertRaises(ServiceError) as raised:
            self.create_kafedra(self.unique("Kafedra Ikki"), qisqa_kodi)
        self.assertEqual(raised.exception.status, 409)

    def test_kafedra_assignment_sets_and_clears(self):
        qisqa_kodi = self.unique("assign-kafedra")
        self.create_kafedra(self.unique("Biriktirish Kafedrasi"), qisqa_kodi)
        created = self.payload(self.create_account(self.unique("assignee"), secrets.token_urlsafe(24), "talaba"))

        assigned = self.payload(self.set_kafedra(created["id"], qisqa_kodi))
        self.assertIsNotNone(assigned["kafedra_id"])

        cleared = self.payload(self.set_kafedra(created["id"], None))
        self.assertIsNone(cleared["kafedra_id"])

    def test_kafedra_assignment_rejects_unknown_code(self):
        created = self.payload(self.create_account(self.unique("badcode"), secrets.token_urlsafe(24), "talaba"))
        with self.assertRaises(ServiceError) as raised:
            self.set_kafedra(created["id"], "no-such-code-" + uuid.uuid4().hex[:8])
        self.assertEqual(raised.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
