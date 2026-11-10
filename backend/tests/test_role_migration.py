"""Migration 008's role-model mapping, committed and re-runnable -- a
destructive role rename on real data can never be re-verified against
production after the fact, so this is the authoritative, permanent check
that the mapping table in backend/migrations/008_role_model_v1.sql actually
does what it claims (docs/decisions.md Sect.18), on top of the throwaway
scripts used to debug it during development.
"""
import unittest
import uuid
from unittest.mock import patch

from backend import auth, manage, persistence
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment
from backend.tests.test_auth import request

# username -> (legacy role, legacy can_submit_to_corpus) -- every old
# role/flag combination migration 008 maps, one row each.
LEGACY_ACCOUNTS = {
    "legacy.admin": ("admin", False),
    "legacy.corpus.manager": ("corpus_manager", False),
    "legacy.reviewer": ("reviewer", False),
    "legacy.user.flagged": ("user", True),
    "legacy.user.flagless": ("user", False),
}
LEGACY_PASSWORD = "Sinov-Tarixiy-Parol-2026!"


_REAL_MIGRATION_FILES = manage.migration_files


def _files_before_008():
    return [(version, content) for version, content in _REAL_MIGRATION_FILES(None)
            if version != "008_role_model_v1"]


class RoleMigrationMappingTests(unittest.TestCase):
    """One owned disposable cluster, migrated up to 007, seeded with
    synthetic legacy-shaped rows (create_user() cannot produce these any
    more, since it only ever accepts the new five roles), then migrated the
    rest of the way so migration 008 runs against real legacy data.
    """

    @classmethod
    def setUpClass(cls):
        cls.cluster = isolated_postgres()
        cls.admin, cls.runtime = cls.cluster.__enter__()
        cls.addClassCleanup(cls.cluster.__exit__, None, None, None)
        with patch.object(manage, "migration_files", side_effect=lambda diagnostic=None: _files_before_008()):
            manage.migrate(cls.admin)
        cls.ids = {}
        with persistence.database(cls.admin) as conn:
            for username, (role, flag) in LEGACY_ACCOUNTS.items():
                user_id = uuid.uuid4()
                conn.execute(
                    "INSERT INTO antiplagiat.users(id,username,password_hash,role,can_submit_to_corpus)"
                    " VALUES (%s,%s,%s,%s,%s)",
                    (user_id, username, auth.password_hash(LEGACY_PASSWORD), role, flag))
                cls.ids[username] = user_id
        manage.migrate(cls.admin)  # now applies 008 against the seeded legacy rows

    def current_roles(self):
        with persistence.database(self.admin) as conn:
            rows = conn.execute(
                "SELECT username, role, can_submit_to_corpus FROM antiplagiat.users"
                " WHERE username = ANY(%s)", (list(LEGACY_ACCOUNTS),)).fetchall()
        return {row["username"]: (row["role"], row["can_submit_to_corpus"]) for row in rows}

    def test_every_legacy_role_flag_combination_maps_exactly_as_specified(self):
        mapped = self.current_roles()
        self.assertEqual(mapped["legacy.admin"], ("admin", False))
        self.assertEqual(mapped["legacy.corpus.manager"], ("kafedra_mudiri", False))
        self.assertEqual(mapped["legacy.reviewer"], ("ustoz", False))
        self.assertEqual(mapped["legacy.user.flagged"], ("ustoz", True))
        self.assertEqual(mapped["legacy.user.flagless"], ("talaba", False))

    def test_super_admin_is_never_auto_assigned_by_the_migration(self):
        with persistence.database(self.admin) as conn:
            count = conn.execute(
                "SELECT count(*) AS n FROM antiplagiat.users WHERE role='super_admin'").fetchone()["n"]
        self.assertEqual(count, 0)

    def test_migrated_accounts_can_still_log_in(self):
        with runtime_environment(self.runtime):
            for username in LEGACY_ACCOUNTS:
                token, user = auth.login(username, LEGACY_PASSWORD)
                self.assertTrue(token)
                self.assertEqual(user["username"], username)

    def test_migrated_accounts_keep_their_prior_corpus_privileges(self):
        # The old corpus_manager account (now kafedra_mudiri) must still pass
        # require_corpus_manager; the old flagless "user" (now talaba) must
        # still be refused it -- role names changed, access did not.
        mapped = self.current_roles()
        with patch.object(auth, "require_user", return_value={
                "id": str(self.ids["legacy.corpus.manager"]), "role": mapped["legacy.corpus.manager"][0]}):
            auth.require_corpus_manager(request())
        with patch.object(auth, "require_user", return_value={
                "id": str(self.ids["legacy.user.flagless"]), "role": mapped["legacy.user.flagless"][0]}):
            with self.assertRaises(persistence.ServiceError) as raised:
                auth.require_corpus_manager(request())
            self.assertEqual(raised.exception.status, 403)
