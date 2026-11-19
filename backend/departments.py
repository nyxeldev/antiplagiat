"""Kafedra (department) CLI operations -- roles-phase1 (docs/decisions.md
Sect.18). Department-level SCOPING of what a kafedra_mudiri sees is phase 2;
this module only lets an operator create kafedralar and assign accounts to
them, via backend.manage's CLI.
"""
import uuid

from psycopg.errors import UniqueViolation

from backend.persistence import database

NAME_MAX = 300
CODE_MAX = 32


def add(config, nomi, qisqa_kodi):
    nomi, qisqa_kodi = nomi.strip(), qisqa_kodi.strip()
    if not nomi or len(nomi) > NAME_MAX:
        raise ValueError(f"Kafedra nomi bo‘sh bo‘lmasligi va {NAME_MAX} belgidan oshmasligi kerak.")
    if not qisqa_kodi or len(qisqa_kodi) > CODE_MAX:
        raise ValueError(f"Qisqa kod bo‘sh bo‘lmasligi va {CODE_MAX} belgidan oshmasligi kerak.")
    kafedra_id = uuid.uuid4()
    with database(config) as conn:
        try:
            conn.execute("INSERT INTO antiplagiat.kafedra(id,nomi,qisqa_kodi) VALUES (%s,%s,%s)",
                         (kafedra_id, nomi, qisqa_kodi))
        except UniqueViolation as error:
            if (error.diag.schema_name == "antiplagiat" and error.diag.table_name == "kafedra"
                    and error.diag.constraint_name == "kafedra_qisqa_kodi_key"):
                raise ValueError("Bu qisqa kod allaqachon band.") from None
            raise
    return kafedra_id


def listing(config):
    with database(config) as conn:
        rows = conn.execute(
            "SELECT id, nomi, qisqa_kodi, created_at FROM antiplagiat.kafedra ORDER BY nomi").fetchall()
    return rows


def assign_user(config, username, qisqa_kodi):
    with database(config) as conn:
        kafedra = conn.execute("SELECT id FROM antiplagiat.kafedra WHERE qisqa_kodi=%s",
                               (qisqa_kodi.strip(),)).fetchone()
        if not kafedra:
            raise ValueError("Bunday qisqa koddagi kafedra topilmadi.")
        row = conn.execute(
            "UPDATE antiplagiat.users SET kafedra_id=%s WHERE username=%s RETURNING id",
            (kafedra["id"], username)).fetchone()
    if not row:
        raise ValueError("Bunday akkaunt topilmadi.")
    return row["id"]
