"""Narrow migration diagnostics: mocked failures and owned PostgreSQL only."""
import contextlib
import io
import logging
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend import manage, persistence
from backend.main import service_error
from backend.tests.postgres_fixture import isolated_postgres


class DiagnosticTests(unittest.TestCase):
    def test_missing_sql_files_are_not_successful_preflight(self):
        diagnostic = manage.MigrationDiagnostics()
        with patch.object(manage.Path, "glob", return_value=[]), self.assertRaises(manage.MigrationError) as raised:
            manage.migration_files(diagnostic)
        diagnostic.record(raised.exception)
        self.assertIn("stage=configuration exception=MigrationError sqlstate=- step=migration_files", diagnostic.summary())

    def cli(self, error=None, config=None):
        output, failure = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["manage", "migrate", "--check", "--diagnostic"]), \
                patch.object(manage, "prompt_database", return_value=config, side_effect=error), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(failure):
            with self.assertRaises(SystemExit) as raised:
                manage.main()
        self.assertEqual(raised.exception.code, 1)
        return output.getvalue() + failure.getvalue()

    def test_configuration_failure_does_not_print_value_or_raw_message(self):
        text = self.cli(error=ValueError("password=private-config DSN-private"))
        self.assertIn("stage=configuration exception=ValueError sqlstate=- step=prompt_database", text)
        self.assertNotIn("private", text)

    def test_connect_failure_preserves_original_class_and_sqlstate(self):
        with patch.object(persistence.psycopg, "connect", side_effect=psycopg.errors.InvalidPassword("private-password private-dsn")):
            text = self.cli(config={"dbname": "synthetic", "password": "private-password"})
        self.assertIn("stage=connect exception=InvalidPassword sqlstate=28P01 step=database_connect", text)
        self.assertNotIn("private", text)
        self.assertNotIn("ServiceError", text)

    def test_file_configuration_valueerror_stays_sanitized_by_wrapper(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        def files(diagnostic):
            if diagnostic:
                diagnostic.mark("configuration", "migration_files")
            raise ValueError("private file content")
        with patch.object(persistence.psycopg, "connect", return_value=conn), \
                patch.object(manage, "migration_files", side_effect=files):
            text = self.cli(config={"dbname": "synthetic"})
            with self.assertRaises(persistence.ServiceError) as raised:
                manage.migrate({"dbname": "synthetic"})
        self.assertIn("stage=configuration exception=ValueError sqlstate=- step=migration_files", text)
        self.assertEqual(raised.exception.code, "database_unavailable")
        self.assertNotIn("private", text + raised.exception.message)

    def test_preflight_query_error_reports_static_step_and_rolls_back_context(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        def execute(statement):
            if statement == "SELECT current_user AS name":
                conn.execute.return_value.fetchone.return_value = {"name": "migration_account"}
            return conn.execute.return_value
        original_error = psycopg.errors.InsufficientPrivilege("private SQL parameters")
        def query(statement, *parameters):
            if statement.startswith("SELECT rolsuper"):
                raise original_error
            return execute(statement)
        conn.execute.side_effect = query
        driver_logger = logging.getLogger("psycopg")
        previous_level = driver_logger.level
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        driver_logger.addHandler(handler)
        self.addCleanup(driver_logger.removeHandler, handler)
        def exit_connection(*args):
            driver_logger.warning("private rollback details and parameters")
            return False
        conn.__exit__.side_effect = exit_connection
        with patch.object(persistence.psycopg, "connect", return_value=conn):
            text = self.cli(config={"dbname": "synthetic"})
        self.assertIn("stage=preflight exception=InsufficientPrivilege sqlstate=42501 step=runtime_role", text)
        self.assertNotIn("private", text)
        self.assertIs(conn.__exit__.call_args.args[1], original_error)
        self.assertEqual(log_output.getvalue(), "")
        self.assertEqual(driver_logger.level, previous_level)

    def test_valueerror_in_migration_is_captured_before_wrapper(self):
        diagnostic = manage.MigrationDiagnostics()
        conn = MagicMock()
        conn.__enter__.return_value = conn
        with patch.object(persistence.psycopg, "connect", return_value=conn):
            with self.assertRaises(persistence.ServiceError) as raised:
                with persistence.database({"dbname": "synthetic"}, diagnostic=diagnostic):
                    diagnostic.mark("migration", "001_accounts_reports")
                    raise ValueError("private bind value")
        self.assertEqual((raised.exception.status, raised.exception.code), (503, "database_unavailable"))
        self.assertIn("stage=migration exception=ValueError sqlstate=- step=001_accounts_reports", diagnostic.summary())
        self.assertNotIn("private", diagnostic.summary())

    def test_commit_error_has_commit_stage_and_safe_fields(self):
        diagnostic = manage.MigrationDiagnostics()
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.closed = False
        conn.__exit__.side_effect = psycopg.errors.ForeignKeyViolation("private row values")
        with patch.object(persistence.psycopg, "connect", return_value=conn):
            with self.assertRaises(persistence.ServiceError):
                with persistence.database({"dbname": "synthetic"}, diagnostic=diagnostic):
                    diagnostic.mark("migration", "record_version")
        self.assertIn("stage=commit exception=ForeignKeyViolation sqlstate=23503 step=transaction_commit", diagnostic.summary())
        self.assertNotIn("private", diagnostic.summary())
        conn.close.assert_called_once()


class HttpSanitizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_body_has_no_diagnostic_metadata(self):
        diagnostic = manage.MigrationDiagnostics()
        with patch.object(persistence.psycopg, "connect", side_effect=psycopg.errors.InvalidPassword("private-password")):
            try:
                with persistence.database({"dbname": "synthetic"}, diagnostic=diagnostic):
                    self.fail("Connect should fail")
            except persistence.ServiceError as error:
                response = await service_error(None, error)
        self.assertEqual(response.status_code, 503)
        text = response.body.decode()
        self.assertIn("database_unavailable", text)
        for value in ("private", "InvalidPassword", "28P01", "diagnostic", "connect"):
            self.assertNotIn(value, text)


def schema_present(config):
    with persistence.database(config) as conn:
        return conn.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='antiplagiat') AS present").fetchone()["present"]


class PostgresMigrationTests(unittest.TestCase):
    def test_read_only_preflight_does_not_create_objects_and_preserves_replay_checksums(self):
        with isolated_postgres() as (admin, _):
            self.assertFalse(schema_present(admin))
            executed, opened = [], []
            class TrackingConnection(psycopg.Connection):
                def execute(self, statement, *args, **kwargs):
                    executed.append(statement)
                    return super().execute(statement, *args, **kwargs)
            def connect(**kwargs):
                conn = TrackingConnection.connect(**kwargs)
                opened.append(conn)
                return conn
            diagnostic = manage.MigrationDiagnostics()
            with patch.object(persistence.psycopg, "connect", side_effect=connect):
                manage.migrate(admin, check=True, diagnostic=diagnostic)
            self.assertEqual(executed[0], "SET TRANSACTION READ ONLY")
            self.assertTrue(all(s.startswith("SELECT ") for s in executed[1:]))
            self.assertFalse(any("advisory" in s for s in executed))
            self.assertTrue(all(conn.closed for conn in opened))
            self.assertFalse(schema_present(admin))
            self.assertIn("stage=preflight exception=none sqlstate=- step=check_complete", diagnostic.summary())
            manage.migrate(admin)
            manage.migrate(admin)
            with persistence.database(admin) as conn:
                before = conn.execute("SELECT * FROM antiplagiat.schema_migrations").fetchall()
            manage.migrate(admin, check=True)
            with persistence.database(admin) as conn:
                self.assertEqual(conn.execute("SELECT * FROM antiplagiat.schema_migrations").fetchall(), before)
                conn.execute("UPDATE antiplagiat.schema_migrations SET checksum='owned-test-change'")
            with self.assertRaises(manage.MigrationError):
                manage.migrate(admin, check=True)
            with self.assertRaises(manage.MigrationError):
                manage.migrate(admin)

    def test_zero_tables_can_still_have_conflicting_function_read_only_check_finds_it(self):
        with isolated_postgres() as (admin, _):
            with persistence.database(admin) as conn:
                conn.execute("CREATE SCHEMA antiplagiat")
                conn.execute("CREATE FUNCTION antiplagiat.guard_report() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END; $$")
                self.assertEqual(conn.execute("SELECT count(*) AS n FROM pg_tables WHERE schemaname='antiplagiat'").fetchone()["n"], 0)
            diagnostic = manage.MigrationDiagnostics()
            with self.assertRaises(manage.MigrationError) as raised:
                manage.migrate(admin, check=True, diagnostic=diagnostic)
            diagnostic.record(raised.exception)
            self.assertIn("stage=preflight exception=MigrationError sqlstate=- step=initial_guard_report", diagnostic.summary())
            with persistence.database(admin) as conn:
                self.assertEqual(conn.execute("SELECT count(*) AS n FROM pg_tables WHERE schemaname='antiplagiat'").fetchone()["n"], 0)
                self.assertTrue(conn.execute("SELECT to_regprocedure('antiplagiat.guard_report()') IS NOT NULL AS present").fetchone()["present"])

    def test_sql_failure_reports_migration_and_rolls_back_all_objects(self):
        with isolated_postgres() as (admin, _):
            diagnostic = manage.MigrationDiagnostics()
            files = [("999_synthetic_failure", "CREATE TABLE antiplagiat.owned_test(id int); SELECT 1/0;")]
            with patch.object(manage, "migration_files", return_value=files), self.assertRaises(persistence.ServiceError):
                manage.migrate(admin, diagnostic=diagnostic)
            self.assertIn("stage=migration exception=DivisionByZero sqlstate=22012 step=999_synthetic_failure", diagnostic.summary())
            self.assertFalse(schema_present(admin))

    def test_deferred_constraint_commit_failure_reports_commit_and_rolls_back(self):
        with isolated_postgres() as (admin, _):
            files = manage.migration_files(None) + [("999_synthetic_commit",
                "CREATE TABLE antiplagiat.owned_parent(id int PRIMARY KEY); "
                "CREATE TABLE antiplagiat.owned_child(id int REFERENCES antiplagiat.owned_parent(id) DEFERRABLE INITIALLY DEFERRED); "
                "INSERT INTO antiplagiat.owned_child VALUES (1);")]
            diagnostic = manage.MigrationDiagnostics()
            opened = []
            original_connect = psycopg.connect
            def connect(**kwargs):
                connection = original_connect(**kwargs)
                opened.append(connection)
                return connection
            with patch.object(manage, "migration_files", return_value=files), \
                    patch.object(persistence.psycopg, "connect", side_effect=connect), \
                    self.assertRaises(persistence.ServiceError):
                manage.migrate(admin, diagnostic=diagnostic)
            self.assertIn("stage=commit exception=ForeignKeyViolation sqlstate=23503 step=transaction_commit", diagnostic.summary())
            self.assertTrue(opened and all(connection.closed for connection in opened))
            self.assertFalse(schema_present(admin))


if __name__ == "__main__":
    unittest.main()
