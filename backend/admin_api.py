"""Admin panel -- roles-phase1 3-bosqich (docs/decisions.md Sect.20): account,
role and kafedra management for admin/super_admin via the web UI, not just
the manage.py CLI. Every endpoint here is require_admin-gated.
"""
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend import auth, departments, manage, rate_limit
from backend.manage import UsernameTakenError
from backend.persistence import ServiceError

router = APIRouter()
HEADERS = {"Cache-Control": "no-store"}
MAX_BODY_BYTES = 4096


async def _read_json_body(request):
    body = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    raise ServiceError("validation_error", "So‘rov tanasi juda uzun.", 400)
                body.extend(chunk)
    except TimeoutError:
        raise ServiceError("upload_interrupted", "So‘rov vaqti tugadi.", 408) from None
    try:
        return json.loads(body)
    except (ValueError, AttributeError, UnicodeError):
        raise ServiceError("validation_error", "So‘rov tanasi noto‘g‘ri JSON.", 400) from None


@router.get("/admin/users")
def search_users(request: Request, q: str = ""):
    admin = auth.require_admin(request)
    rate_limit.enforce(admin["id"], "admin")
    return JSONResponse({"items": manage.search_users(None, q)}, headers=HEADERS)


@router.post("/admin/users")
async def create_account(request: Request):
    admin = await run_in_threadpool(auth.require_admin, request)
    rate_limit.enforce(admin["id"], "admin")
    body = await _read_json_body(request)
    username, password, role = body.get("username"), body.get("password"), body.get("role")
    if role == "super_admin":
        raise ServiceError("validation_error", "super_admin faqat CLI orqali beriladi.", 400)
    if not isinstance(username, str) or not isinstance(password, str) or not isinstance(role, str):
        raise ServiceError("validation_error", "username/password/role majburiy.", 400)
    try:
        user_id = manage.create_user(None, username, password, role)
    except UsernameTakenError as error:
        raise ServiceError("username_taken", str(error), 409) from None
    except ValueError as error:
        raise ServiceError("validation_error", str(error), 400) from None
    return JSONResponse({"id": str(user_id), "username": username, "role": role}, headers=HEADERS, status_code=201)


@router.post("/admin/users/{user_id}/role")
async def set_role(request: Request, user_id: str):
    admin = await run_in_threadpool(auth.require_admin, request)
    rate_limit.enforce(admin["id"], "admin")
    body = await _read_json_body(request)
    return JSONResponse(auth.set_role(user_id, body.get("role")), headers=HEADERS)


@router.post("/admin/users/{user_id}/kafedra")
async def set_kafedra(request: Request, user_id: str):
    admin = await run_in_threadpool(auth.require_admin, request)
    rate_limit.enforce(admin["id"], "admin")
    body = await _read_json_body(request)
    return JSONResponse(auth.set_kafedra(user_id, body.get("qisqa_kodi")), headers=HEADERS)


@router.post("/admin/users/{user_id}/enabled")
async def set_enabled(request: Request, user_id: str):
    admin = await run_in_threadpool(auth.require_admin, request)
    rate_limit.enforce(admin["id"], "admin")
    body = await _read_json_body(request)
    return JSONResponse(auth.set_enabled(user_id, body.get("enabled"), admin["id"]), headers=HEADERS)


@router.get("/admin/kafedra")
def list_kafedra(request: Request):
    admin = auth.require_admin(request)
    rate_limit.enforce(admin["id"], "admin")
    rows = departments.listing(None)
    return JSONResponse({"items": [{"id": str(row["id"]), "nomi": row["nomi"], "qisqa_kodi": row["qisqa_kodi"],
                                    "created_at": row["created_at"].isoformat()} for row in rows]}, headers=HEADERS)


@router.post("/admin/kafedra")
async def create_kafedra(request: Request):
    admin = await run_in_threadpool(auth.require_admin, request)
    rate_limit.enforce(admin["id"], "admin")
    body = await _read_json_body(request)
    nomi, qisqa_kodi = body.get("nomi"), body.get("qisqa_kodi")
    if not isinstance(nomi, str) or not isinstance(qisqa_kodi, str):
        raise ServiceError("validation_error", "nomi/qisqa_kodi majburiy.", 400)
    try:
        kafedra_id = departments.add(None, nomi, qisqa_kodi)
    except ValueError as error:
        # The duplicate-code case raises ServiceError(409) directly and
        # passes through untouched; only the length/blank validation at the
        # top of departments.add() still raises a plain ValueError here.
        raise ServiceError("validation_error", str(error), 400) from None
    return JSONResponse({"id": str(kafedra_id), "nomi": nomi, "qisqa_kodi": qisqa_kodi},
                        headers=HEADERS, status_code=201)
