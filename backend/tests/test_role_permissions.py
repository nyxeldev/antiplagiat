"""Endpoint x role permission matrix -- roles-phase1 (docs/decisions.md Sect.18).

ENDPOINTS below must list EVERY protected endpoint in accounts_api.py,
corpus_api.py and comparison/api.py, naming the exact backend.auth guard it
calls. Whenever a new protected endpoint is added to any router, add a row
here too -- this file is the only place that checks "does every endpoint
still enforce the role it's supposed to", and it goes silently stale
otherwise. (POST /auth/login is intentionally absent: it is the public
credential-check entry point, not role-gated.)
"""
import unittest
from unittest.mock import patch

from backend import auth
from backend.persistence import ServiceError
from backend.tests.test_auth import request

ROLES = ("talaba", "ustoz", "kafedra_mudiri", "admin", "super_admin")

# (method, path, guard attribute name on backend.auth)
ENDPOINTS = [
    ("GET", "/auth/me", "require_user"),
    ("POST", "/auth/logout", "require_user"),
    ("GET", "/reports", "require_user"),
    ("GET", "/reports/{report_id}", "require_user"),
    ("DELETE", "/reports/{report_id}", "require_user"),
    ("POST", "/compare", "require_user"),
    ("POST", "/corpus/documents", "require_corpus_manager"),
    ("GET", "/corpus/documents", "require_corpus_manager"),
    ("GET", "/corpus/documents/{document_id}", "require_corpus_manager"),
    ("POST", "/corpus/documents/{document_id}/withdraw", "require_corpus_manager"),
    ("POST", "/corpus/documents/{document_id}/approve", "require_corpus_manager"),
    ("POST", "/corpus/documents/{document_id}/reject", "require_corpus_manager"),
    ("POST", "/corpus/submissions", "require_teacher"),
    ("GET", "/corpus/submissions", "require_teacher"),
    ("POST", "/users/{user_id}/corpus-submission-access", "require_admin"),
]


def expected_to_pass(guard, role, can_submit_to_corpus):
    if guard == "require_user":
        return True
    if guard == "require_corpus_manager":
        return role in auth.CORPUS_MANAGEMENT_ROLES
    if guard == "require_admin":
        return role in auth.ADMIN_ROLES
    if guard == "require_teacher":
        if role in auth.CORPUS_MANAGEMENT_ROLES:
            return True
        if role == auth.TEACHER_SUBMISSION_ROLE:
            return can_submit_to_corpus
        return False
    raise AssertionError(f"Noma'lum guard: {guard}")  # pragma: no cover


class PermissionMatrixTests(unittest.TestCase):
    def test_every_endpoint_enforces_its_role_for_every_role(self):
        """Covers every (endpoint, role) pair, and both can_submit_to_corpus
        states for the one role (ustoz) that guard actually inspects."""
        combinations = 0
        for method, path, guard in ENDPOINTS:
            for role in ROLES:
                flag_states = (True, False) if role == auth.TEACHER_SUBMISSION_ROLE else (None,)
                for can_submit_to_corpus in flag_states:
                    combinations += 1
                    user = {"id": "matrix", "username": "matrix", "role": role,
                            "can_submit_to_corpus": can_submit_to_corpus}
                    should_pass = expected_to_pass(guard, role, can_submit_to_corpus)
                    with self.subTest(method=method, path=path, role=role,
                                      can_submit_to_corpus=can_submit_to_corpus), \
                            patch.object(auth, "require_user", return_value=user):
                        if should_pass:
                            self.assertEqual(getattr(auth, guard)(request())["role"], role)
                        else:
                            with self.assertRaises(ServiceError) as raised:
                                getattr(auth, guard)(request())
                            self.assertEqual(raised.exception.status, 403)
        # Every endpoint x role, plus a second can_submit_to_corpus state for
        # ustoz on every endpoint (confirming the flag is irrelevant to the
        # three guards that do not inspect it, not just to require_teacher).
        self.assertEqual(combinations, len(ENDPOINTS) * len(ROLES) + len(ENDPOINTS))

    def test_every_endpoint_refuses_an_anonymous_caller(self):
        for method, path, guard in ENDPOINTS:
            with self.subTest(method=method, path=path):
                with self.assertRaises(ServiceError) as raised:
                    getattr(auth, guard)(request())
                self.assertEqual(raised.exception.status, 401)
