import json
import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend import auth, reports
from backend.persistence import ServiceError

router = APIRouter()
HEADERS = {"Cache-Control": "no-store"}


@router.post("/auth/login")
async def login(request: Request):
    auth.guard(request)
    auth.limiter.check(request.client.host)
    body = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                if len(body) + len(chunk) > 8192:
                    raise ServiceError("credentials", "Login yoki parol noto‘g‘ri.", 401)
                body.extend(chunk)
    except TimeoutError:
        raise ServiceError("login_timeout", "Kirish so‘rovi vaqti tugadi.", 408) from None
    try:
        supplied = json.loads(body)
        username, password = supplied.get("username"), supplied.get("password")
    except (ValueError, AttributeError, UnicodeError):
        username, password = None, None
    if not auth.valid_username(username) or not isinstance(password, str) or not 1 <= len(password) <= 256:
        raise ServiceError("credentials", "Login yoki parol noto‘g‘ri.", 401)
    token, user = await run_in_threadpool(auth.login, username, password, request.cookies.get(auth.COOKIE))
    result = JSONResponse({"user": user}, headers=HEADERS)
    result.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True,
                      secure=auth.public_origin().startswith("https://"), samesite="strict", path="/")
    return result


@router.get("/auth/me")
def me(request: Request):
    return JSONResponse({"user": auth.require_user(request)}, headers=HEADERS)


@router.post("/auth/logout")
def logout(request: Request):
    auth.logout(request)
    result = JSONResponse({"status": "logged_out"}, headers=HEADERS)
    result.delete_cookie(auth.COOKIE, httponly=True, secure=auth.public_origin().startswith("https://"), samesite="strict", path="/")
    return result


@router.get("/reports")
def history(request: Request, page: int = Query(1, ge=1, le=100000)):
    owner = auth.require_user(request)["id"]
    return JSONResponse(reports.history(owner, page), headers=HEADERS)


@router.get("/reports/{report_id}")
def get_report(request: Request, report_id: str):
    owner = auth.require_user(request)["id"]
    try:
        key = reports.request_key(report_id)
    except ServiceError:
        raise ServiceError("not_found", "Hisobot topilmadi.", 404) from None
    return JSONResponse(reports.get(owner, key), headers=HEADERS)


@router.delete("/reports/{report_id}")
def delete_report(request: Request, report_id: str):
    owner = auth.require_user(request)["id"]
    try:
        key = reports.request_key(report_id)
    except ServiceError:
        raise ServiceError("not_found", "Hisobot topilmadi.", 404) from None
    reports.delete(owner, key)
    return JSONResponse({"status": "deleted"}, headers=HEADERS)
