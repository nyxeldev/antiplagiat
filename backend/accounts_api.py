import json
import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from backend import auth, rate_limit, reports
from backend.persistence import ServiceError

router = APIRouter()
HEADERS = {"Cache-Control": "no-store"}
MAX_BODY_BYTES = 4096
MAX_AVATAR_BODY_BYTES = auth.MAX_AVATAR_BYTES + 16 * 1024
AVATAR_SECONDS = 20


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
    user = auth.require_user(request)
    return JSONResponse({"user": auth.get_profile(user["id"])}, headers=HEADERS)


@router.post("/auth/change-password")
async def change_password(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    body = await _read_json_body(request)
    old_password, new_password = body.get("old_password"), body.get("new_password")
    if not isinstance(old_password, str) or not isinstance(new_password, str):
        raise ServiceError("validation_error", "old_password/new_password majburiy.", 400)
    payload = await run_in_threadpool(auth.change_password, user["id"], old_password, new_password)
    # change_password() already deleted every session for this account server-side
    # (including the one behind this very request) -- drop the now-dead cookie here
    # too, instead of leaving the browser to find out only on its next 401.
    result = JSONResponse(payload, headers=HEADERS)
    result.delete_cookie(auth.COOKIE, httponly=True, secure=auth.public_origin().startswith("https://"), samesite="strict", path="/")
    return result


@router.post("/auth/full-name")
async def set_full_name(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    body = await _read_json_body(request)
    full_name = body.get("full_name")
    if not isinstance(full_name, str):
        raise ServiceError("validation_error", "full_name majburiy.", 400)
    return JSONResponse(await run_in_threadpool(auth.set_full_name, user["id"], full_name), headers=HEADERS)


@router.post("/auth/username")
async def set_username(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    body = await _read_json_body(request)
    new_username = body.get("username")
    if not isinstance(new_username, str):
        raise ServiceError("validation_error", "username majburiy.", 400)
    return JSONResponse(await run_in_threadpool(auth.set_username, user["id"], new_username), headers=HEADERS)


class AvatarUpload:
    """A single small 'file' part, buffered in memory -- avatars are stored
    as bytea (see migration 010), never written to disk, so there is no temp
    file to stream into here the way CorpusUpload (corpus_api.py) does.
    """

    def __init__(self, content_type):
        mime, options = parse_options_header(content_type)
        boundary = options.get(b"boundary", b"")
        if mime != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
            raise ServiceError("upload_format", "multipart/form-data yuklash formati kerak.", 400)
        self.body_size, self.file_size = 0, 0
        self.data, self.role, self.finished = bytearray(), None, False
        callbacks = {"on_" + n: getattr(self, n) for n in (
            "part_begin", "header_field", "header_value", "header_end", "headers_finished",
            "part_data", "part_end", "end")}
        self.parser = MultipartParser(boundary, callbacks)

    def part_begin(self):
        self.headers, self.field, self.value = {}, bytearray(), bytearray()
        self.header_size, self.role = 0, None

    def header_field(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 4096:
            raise ServiceError("upload_format", "Fayl sarlavhasi juda uzun.", 400)
        self.field.extend(data[start:end])

    def header_value(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 4096:
            raise ServiceError("upload_format", "Fayl sarlavhasi juda uzun.", 400)
        self.value.extend(data[start:end])

    def header_end(self):
        self.headers[bytes(self.field).lower()] = bytes(self.value)
        self.field.clear()
        self.value.clear()

    def headers_finished(self):
        disposition, options = parse_options_header(self.headers.get(b"content-disposition", b""))
        name = options.get(b"name", b"").decode("ascii", errors="replace")
        if disposition != b"form-data" or name != "file":
            raise ServiceError("upload_format", "'file' maydoni kerak.", 400)
        self.role = "file"

    def part_data(self, data, start, end):
        self.file_size += end - start
        if self.file_size > auth.MAX_AVATAR_BYTES:
            raise ServiceError("file_limit", "Rasm 1 MiB dan oshmasligi kerak.", 413)
        self.data.extend(data[start:end])

    def part_end(self):
        pass

    def end(self):
        self.finished = True

    def write(self, data):
        self.body_size += len(data)
        if self.body_size > MAX_AVATAR_BODY_BYTES:
            raise ServiceError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
        self.parser.write(data)

    def finish(self):
        self.parser.finalize()
        if not self.finished or not self.data:
            raise ServiceError("incomplete_upload", "Rasm yuklash to‘liq tugamadi.", 400)
        return bytes(self.data)


@router.post("/auth/avatar")
async def upload_avatar(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    length = request.headers.get("content-length")
    if length and (not length.isdecimal() or int(length) > MAX_AVATAR_BODY_BYTES):
        raise ServiceError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
    upload = AvatarUpload(request.headers.get("content-type", ""))
    try:
        async with asyncio.timeout(AVATAR_SECONDS):
            async for chunk in request.stream():
                upload.write(chunk)
        raw = upload.finish()
    except (ServiceError, TimeoutError, ClientDisconnect):
        raise
    except Exception:
        raise ServiceError("upload_format", "Yuklash formati buzilgan.", 400) from None
    return JSONResponse(await run_in_threadpool(auth.set_avatar, user["id"], raw), headers=HEADERS)


@router.delete("/auth/avatar")
async def delete_avatar(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    return JSONResponse(await run_in_threadpool(auth.clear_avatar, user["id"]), headers=HEADERS)


@router.get("/auth/avatar/{user_id}")
def get_avatar(request: Request, user_id: str):
    auth.require_user(request)
    raw, mime = auth.get_avatar(user_id)
    return Response(content=raw, media_type=mime,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/auth/sessions")
def list_sessions(request: Request):
    user = auth.require_user(request)
    return JSONResponse(auth.list_sessions(user["id"], request.cookies.get(auth.COOKIE)), headers=HEADERS)


@router.post("/auth/sessions/revoke-others")
async def revoke_other_sessions(request: Request):
    user = await run_in_threadpool(auth.require_user, request)
    rate_limit.enforce(user["id"], "account")
    token = request.cookies.get(auth.COOKIE)
    return JSONResponse(await run_in_threadpool(auth.revoke_other_sessions, user["id"], token), headers=HEADERS)


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
