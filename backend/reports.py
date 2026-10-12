"""Every query is owner scoped, including retries and deletion tombstones."""
import hashlib
import json
import uuid

from psycopg.types.json import Jsonb

from backend.persistence import ServiceError, database


def request_key(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ServiceError("request_key", "Tekshiruv identifikatori noto‘g‘ri.", 400) from None


def fingerprint(folder, items):
    digest = hashlib.sha256()
    for item in items:
        descriptor = json.dumps([item["role"], item["name"]], ensure_ascii=False).encode()
        digest.update(len(descriptor).to_bytes(8, "big"))
        digest.update(descriptor)
        path = folder / item["path"]
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            while chunk := stream.read(65536):
                digest.update(chunk)
    return digest.hexdigest()


def response(row):
    return {**row["snapshot"], "report_id": str(row["id"]),
            "created_at": row["created_at"].isoformat(), "saved": True}


def retry(owner, key, digest):
    with database() as conn:
        row = conn.execute("SELECT id,created_at,snapshot,input_digest,deleted_at FROM antiplagiat.reports WHERE owner_id=%s AND request_key=%s", (owner, key)).fetchone()
    if row:
        if row["input_digest"] != digest:
            raise ServiceError("request_conflict", "Shu identifikator bilan boshqa fayllar yuborilgan.", 409)
        if row["deleted_at"]:
            raise ServiceError("report_deleted", "Ushbu tekshiruv o‘chirilgan. Yangi tekshiruv boshlang.", 410)
        return response(row)
    return None


def save(owner, key, digest, snapshot):
    with database() as conn:
        row = conn.execute("INSERT INTO antiplagiat.reports(id,owner_id,request_key,input_digest,algorithm_version,normalization_version,snapshot) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (owner_id,request_key) DO NOTHING RETURNING id,created_at,snapshot",
                           (uuid.uuid4(), owner, key, digest, snapshot["parameters"]["algorithm_version"],
                            snapshot["parameters"]["normalization_version"], Jsonb(snapshot))).fetchone()
    # Commit has completed before any response can claim it was saved.
    if row:
        return response(row)
    previous = retry(owner, key, digest)
    if previous is None:
        raise ServiceError("report_conflict", "Hisobotni saqlash natijasini tasdiqlab bo‘lmadi. Qayta urinib ko‘ring.", 409)
    return previous


def history(owner, page):
    with database() as conn:
        rows = conn.execute("SELECT id,created_at,algorithm_version,normalization_version,snapshot->'document'->>'name' AS name,snapshot->>'coverage_percent' AS coverage_percent FROM antiplagiat.reports WHERE owner_id=%s AND deleted_at IS NULL ORDER BY created_at DESC,id DESC LIMIT 21 OFFSET %s", (owner, (page - 1) * 20)).fetchall()
    return {"page": page, "has_next": len(rows) > 20,
            "items": [{**r, "id": str(r["id"]), "created_at": r["created_at"].isoformat(),
                       "coverage_percent": float(r["coverage_percent"])} for r in rows[:20]]}


def get(owner, report_id):
    with database() as conn:
        row = conn.execute("SELECT id,created_at,snapshot FROM antiplagiat.reports WHERE owner_id=%s AND id=%s AND deleted_at IS NULL", (owner, report_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Hisobot topilmadi.", 404)
    return response(row)


def delete(owner, report_id):
    with database() as conn:
        row = conn.execute("UPDATE antiplagiat.reports SET snapshot=NULL,deleted_at=now() WHERE owner_id=%s AND id=%s AND deleted_at IS NULL RETURNING id", (owner, report_id)).fetchone()
    if not row:
        raise ServiceError("not_found", "Hisobot topilmadi.", 404)
