import os

import psycopg


CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 3000


def database_ready() -> bool:
    # Read configuration per request; never connect during import.
    settings = {
        key: os.environ.get(f"ANTIPLAGIAT_DB_{name}", "")
        for key, name in (
            ("host", "HOST"),
            ("port", "PORT"),
            ("dbname", "NAME"),
            ("user", "USER"),
            ("password", "PASSWORD"),
        )
    }
    if any(not value.strip() for value in settings.values()):
        return False
    port = settings["port"]
    if not port.isascii() or not port.isdecimal() or len(port) > 5:
        return False
    if not 1 <= int(port) <= 65535:
        return False
    try:
        with psycopg.connect(
            **settings,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except (psycopg.Error, ValueError):
        # Never expose credentials, connection strings or raw driver errors.
        return False
