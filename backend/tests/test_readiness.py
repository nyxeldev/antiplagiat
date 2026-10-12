import importlib
import json
import os
import unittest
from unittest.mock import patch

import psycopg

from backend import database, main


CONFIG = {
    "ANTIPLAGIAT_DB_HOST": "127.0.0.1",
    "ANTIPLAGIAT_DB_PORT": "5432",
    "ANTIPLAGIAT_DB_NAME": "antiplagiat",
    "ANTIPLAGIAT_DB_USER": "antiplagiat_app",
    "ANTIPLAGIAT_DB_PASSWORD": "synthetic-test-password",
}


class ReadinessTests(unittest.TestCase):
    def assert_not_ready(self):
        response = main.ready()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body), {"status": "not_ready"})

    def test_success_and_timeouts(self):
        with patch.dict(os.environ, CONFIG, clear=True), patch.object(
            database.psycopg, "connect"
        ) as connect:
            connection = connect.return_value.__enter__.return_value
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            response = main.ready()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.body), {"status": "ready"})
            cursor.execute.assert_called_once_with("SELECT 1")
            self.assertEqual(connect.call_args.kwargs["connect_timeout"], 3)
            self.assertEqual(connect.call_args.kwargs["options"], "-c statement_timeout=3000")
            self.assertTrue(connect.call_args.kwargs["autocommit"])
            connect.return_value.__exit__.assert_called_once()
            connection.cursor.return_value.__exit__.assert_called_once()

    def test_missing_and_blank_configuration(self):
        for key in CONFIG:
            for value in (None, "", "   "):
                config = CONFIG.copy()
                if value is None:
                    del config[key]
                else:
                    config[key] = value
                with self.subTest(key=key, value=value), patch.dict(
                    os.environ, config, clear=True
                ), patch.object(database.psycopg, "connect") as connect:
                    self.assert_not_ready()
                    connect.assert_not_called()

    def test_invalid_ports(self):
        for port in ("0", "65536", "-1", "abc", "5432.0", " 5432", "５４３２", "9" * 5000):
            with self.subTest(port=port[:10]), patch.dict(
                os.environ, {**CONFIG, "ANTIPLAGIAT_DB_PORT": port}, clear=True
            ), patch.object(database.psycopg, "connect") as connect:
                self.assert_not_ready()
                connect.assert_not_called()

    def test_connection_error_is_sanitized(self):
        with patch.dict(os.environ, CONFIG, clear=True), patch.object(
            database.psycopg, "connect", side_effect=psycopg.OperationalError(
                "synthetic-test-password raw connection error"
            )
        ):
            self.assert_not_ready()

    def test_statement_error_closes_connection(self):
        with patch.dict(os.environ, CONFIG, clear=True), patch.object(
            database.psycopg, "connect"
        ) as connect:
            connection = connect.return_value.__enter__.return_value
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.execute.side_effect = psycopg.OperationalError("statement timeout")
            self.assert_not_ready()
            connect.return_value.__exit__.assert_called_once()
            connection.cursor.return_value.__exit__.assert_called_once()

    def test_unexpected_result_is_not_ready(self):
        for result in (None, (2,)):
            with self.subTest(result=result), patch.dict(
                os.environ, CONFIG, clear=True
            ), patch.object(database.psycopg, "connect") as connect:
                cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = result
                self.assert_not_ready()

    def test_import_does_not_connect_and_health_is_unchanged(self):
        with patch.dict(os.environ, CONFIG, clear=True), patch.object(
            database.psycopg, "connect"
        ) as connect:
            importlib.reload(database)
            importlib.reload(main)
            connect.assert_not_called()
            with patch.object(main, "database_ready") as database_ready:
                self.assertEqual(main.health(), {"status": "ok"})
                database_ready.assert_not_called()
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
