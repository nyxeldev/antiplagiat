"""Short-lived psycopg transactions; credentials and driver errors stay private."""
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


class ServiceError(Exception):
    def __init__(self, code, message, status):
        self.code, self.message, self.status = code, message, status


def settings(prefix="ANTIPLAGIAT_DB_"):
    values = {key: os.environ.get(prefix + name, "") for key, name in
              (("host", "HOST"), ("port", "PORT"), ("dbname", "NAME"),
               ("user", "USER"), ("password", "PASSWORD"))}
    port = values["port"]
    if (any(not v.strip() for v in values.values()) or not port.isascii()
            or not port.isdecimal() or len(port) > 5 or not 1 <= int(port) <= 65535):
        raise ServiceError("database_unavailable", "Ma’lumotlar bazasi hozir mavjud emas.", 503)
    return values


@contextmanager
def database(config=None, *, diagnostic=None):
    connection = None
    try:
        if diagnostic:
            diagnostic("configuration")
        configured = config or settings()
        if diagnostic:
            diagnostic("connect")
        connection = psycopg.connect(**configured, connect_timeout=3,
                                     options="-c statement_timeout=5000 -c lock_timeout=3000",
                                     row_factory=dict_row)
        with connection:
            yield connection
            if diagnostic:
                diagnostic("commit")
    except (psycopg.Error, ValueError) as error:
        if diagnostic:
            diagnostic(None, error)
        raise ServiceError("database_unavailable", "Ma’lumotlar bazasi hozir mavjud emas.", 503) from None
    finally:
        # psycopg __exit__ does not reach close() when commit itself raises.
        if connection is not None and not connection.closed:
            connection.close()
