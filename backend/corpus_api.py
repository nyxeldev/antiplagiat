"""Admin-only corpus administration endpoints.

Uploads are streamed to a temporary file and parsed by the sandboxed worker, the
same way personal comparisons are. Nothing here reads a personal report.
"""
import asyncio
import json
import tempfile
import threading
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from backend import auth, corpus, rate_limit
from backend.comparison.policy import ComparisonError, MAX_FILE_BYTES, UPLOAD_SECONDS
from backend.comparison.runner import run_worker
from backend.persistence import ServiceError

router = APIRouter()
HEADERS = {"Cache-Control": "no-store"}
gate = threading.Lock()  # One corpus ingest at a time; the worker is single use.
MAX_CORPUS_BODY_BYTES = MAX_FILE_BYTES + 64 * 1024
TEXT_FIELDS = ("title", "author_display", "doc_type", "year", "language_hint",
               "source_note", "permission_basis", "visibility")


class CorpusUpload:
    """One file plus small text fields, bounded while streaming."""

    def __init__(self, folder, content_type):
        mime, options = parse_options_header(content_type)
        boundary = options.get(b"boundary", b"")
        if mime != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
            raise ComparisonError("upload_format", "multipart/form-data yuklash formati kerak.", 400)
        self.folder, self.fields, self.stream = folder, {}, None
        self.body_size = self.file_size = 0
        self.name = self.role = None
        self.finished = False
        callbacks = {"on_" + n: getattr(self, n) for n in (
            "part_begin", "header_field", "header_value", "header_end", "headers_finished",
            "part_data", "part_end", "end")}
        self.parser = MultipartParser(boundary, callbacks)

    def part_begin(self):
        self.headers, self.field, self.value = {}, bytearray(), bytearray()
        self.header_size, self.file_size = 0, 0
        self.role, self.text = None, bytearray()

    def header_field(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            raise ComparisonError("headers_limit", "Fayl sarlavhasi juda uzun.", 400)
        self.field.extend(data[start:end])

    def header_value(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            raise ComparisonError("headers_limit", "Fayl sarlavhasi juda uzun.", 400)
        self.value.extend(data[start:end])

    def header_end(self):
        field = bytes(self.field).lower()
        if field in self.headers:
            raise ComparisonError("upload_format", "Takrorlangan fayl sarlavhasi.", 400)
        self.headers[field] = bytes(self.value)
        self.field.clear()
        self.value.clear()

    def headers_finished(self):
        disposition, options = parse_options_header(self.headers.get(b"content-disposition", b""))
        role = options.get(b"name", b"").decode("ascii", errors="replace")
        if disposition != b"form-data":
            raise ComparisonError("upload_format", "form-data maydonlari kerak.", 400)
        if role == "file":
            if self.stream is not None or b"filename" not in options:
                raise ComparisonError("upload_format", "Bitta fayl maydoni kerak.", 400)
            raw = options[b"filename"].decode("utf-8", errors="replace")
            name = raw.replace("\\", "/").rsplit("/", 1)[-1]
            name = "".join(c for c in name if not unicodedata.category(c).startswith("C"))
            if not name or len(name) > 200:
                raise ComparisonError("filename", "Fayl nomi bo‘sh yoki juda uzun.", 400)
            if Path(name).suffix.lower() not in (".txt", ".pdf", ".docx"):
                raise ComparisonError("unsupported", "Faqat TXT, DOCX va PDF qabul qilinadi.", 415, name)
            self.name = name
            self.stream = (self.folder / "corpus-upload").open("xb")
            self.role = "file"
        elif role in TEXT_FIELDS:
            self.role = role
        else:
            raise ComparisonError("upload_format", "Noma’lum maydon yuborildi.", 400)

    def part_data(self, data, start, end):
        if self.role == "file":
            self.file_size += end - start
            if self.file_size > MAX_FILE_BYTES:
                raise ComparisonError("file_limit", "Bitta fayl 10 MiB dan oshmasligi kerak.", 413)
            self.stream.write(data[start:end])
        elif self.role:
            self.text.extend(data[start:end])
            if len(self.text) > 4096:
                raise ComparisonError("corpus_metadata", "Metama’lumot maydoni juda uzun.", 400)

    def part_end(self):
        if self.role == "file":
            self.close()
        elif self.role:
            self.fields[self.role] = bytes(self.text).decode("utf-8", errors="replace")

    def end(self):
        self.finished = True

    def write(self, data):
        self.body_size += len(data)
        if self.body_size > MAX_CORPUS_BODY_BYTES:
            raise ComparisonError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
        self.parser.write(data)

    def finish(self):
        self.parser.finalize()
        if not self.finished or self.stream is not None or not self.name:
            raise ComparisonError("incomplete_upload", "Fayl yuklash to‘liq tugamadi.", 400)
        year = self.fields.get("year", "").strip()
        metadata = {k: self.fields.get(k, "") for k in TEXT_FIELDS if k != "year"}
        metadata["original_filename"] = self.name
        if year:
            if not year.isdecimal() or len(year) > 4:
                raise ComparisonError("corpus_metadata", "Yil butun son bo‘lishi kerak.", 400)
            metadata["year"] = int(year)
        else:
            metadata["year"] = None
        return metadata

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def ingest(folder, name, metadata, uploaded_by, review_status="approved"):
    """Parse in the sandboxed worker, then store the extracted text."""
    extracted = run_worker(folder, {"mode": "extract", "items": [{"path": "corpus-upload", "name": name}]})
    document = extracted["documents"][0]
    raw = (folder / "corpus-upload").read_bytes()
    return corpus.add_document(metadata, document, uploaded_by, raw, review_status=review_status)


async def _accept_upload(request, uploaded_by, review_status, status_label):
    """Shared by the admin/corpus_manager direct-add path and the teacher
    submission path below -- identical streaming, parsing and error
    handling; only who is storing it and what review_status/status label
    the result gets differ.
    """
    if not gate.acquire(blocking=False):
        return JSONResponse(ComparisonError("busy", "Boshqa korpus yuklash davom etmoqda.", 429).payload(), 429, headers=HEADERS)
    try:
        length = request.headers.get("content-length")
        if length and (not length.isdecimal() or int(length) > MAX_CORPUS_BODY_BYTES):
            raise ComparisonError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
        with tempfile.TemporaryDirectory(prefix="antiplagiat-corpus-") as directory:
            folder = Path(directory)
            upload = CorpusUpload(folder, request.headers.get("content-type", ""))
            try:
                async with asyncio.timeout(UPLOAD_SECONDS):
                    async for chunk in request.stream():
                        upload.write(chunk)
                metadata = upload.finish()
            except (ComparisonError, ServiceError, TimeoutError, ClientDisconnect):
                raise
            except Exception:
                raise ComparisonError("upload_format", "Yuklash formati buzilgan.", 400) from None
            finally:
                upload.close()
            stored = await run_in_threadpool(ingest, folder, upload.name, metadata, uploaded_by, review_status)
        return JSONResponse({"status": status_label, **stored}, headers=HEADERS)
    except (ServiceError, ComparisonError) as error:
        if isinstance(error, ServiceError):
            raise
        return JSONResponse(error.payload(), error.status, headers=HEADERS)
    except (TimeoutError, ClientDisconnect):
        return JSONResponse(ComparisonError("upload_interrupted", "Yuklash uzildi yoki vaqt chegarasidan oshdi.", 408).payload(), 408, headers=HEADERS)
    except Exception:
        return JSONResponse(ComparisonError("server_error", "Korpusga qo‘shib bo‘lmadi.", 500).payload(), 500, headers=HEADERS)
    finally:
        gate.release()


@router.post("/corpus/documents")
async def add(request: Request):
    manager = await run_in_threadpool(auth.require_corpus_manager, request)
    await run_in_threadpool(rate_limit.enforce, manager["id"], "corpus")
    return await _accept_upload(request, manager["id"], "approved", "added")


@router.post("/corpus/submissions")
async def submit(request: Request):
    """A teacher's own moderated upload: stored immediately, like the admin
    path, but excluded from retrieval (review_status="pending") until a
    corpus_manager/admin approves it below.
    """
    teacher = await run_in_threadpool(auth.require_teacher, request)
    await run_in_threadpool(rate_limit.enforce, teacher["id"], "corpus")
    return await _accept_upload(request, teacher["id"], "pending", "pending")


@router.get("/corpus/submissions")
def my_submissions(request: Request, page: int = 1):
    """A teacher sees every status of their own submissions (pending,
    approved, rejected, withdrawn) and never another teacher's.
    """
    teacher = auth.require_teacher(request)
    rate_limit.enforce(teacher["id"], "corpus")
    return JSONResponse(corpus.list_documents(page, "all", uploaded_by=teacher["id"]), headers=HEADERS)


@router.get("/corpus/documents")
def listing(request: Request, page: int = 1, status: str = "active", review_status: str | None = None):
    manager = auth.require_corpus_manager(request)
    rate_limit.enforce(manager["id"], "corpus")
    return JSONResponse(corpus.list_documents(page, status, review_status=review_status), headers=HEADERS)


@router.get("/corpus/documents/{document_id}")
def detail(request: Request, document_id: str):
    manager = auth.require_corpus_manager(request)
    rate_limit.enforce(manager["id"], "corpus")
    return JSONResponse(corpus.get_document(document_id), headers=HEADERS)


@router.post("/corpus/documents/{document_id}/withdraw")
def withdraw(request: Request, document_id: str):
    manager = auth.require_corpus_manager(request)
    rate_limit.enforce(manager["id"], "corpus")
    return JSONResponse(corpus.withdraw(document_id), headers=HEADERS)


@router.post("/corpus/documents/{document_id}/approve")
def approve(request: Request, document_id: str):
    manager = auth.require_corpus_manager(request)
    rate_limit.enforce(manager["id"], "corpus")
    return JSONResponse(corpus.approve(document_id), headers=HEADERS)


@router.post("/users/{user_id}/corpus-submission-access")
async def set_submission_access(request: Request, user_id: str):
    """Admin-only grant/revoke of a "user"-role account's right to submit to
    the corpus moderation queue (backend/auth.py's can_submit_to_corpus flag,
    see docs/decisions.md §12). Body: {"enabled": true|false}.
    """
    admin = await run_in_threadpool(auth.require_admin, request)
    await run_in_threadpool(rate_limit.enforce, admin["id"], "corpus")
    body = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4096:
                    raise corpus.CorpusError("corpus_metadata", "So‘rov tanasi juda uzun.", 400)
                body.extend(chunk)
    except TimeoutError:
        raise corpus.CorpusError("upload_interrupted", "So‘rov vaqti tugadi.", 408) from None
    try:
        enabled = json.loads(body).get("enabled")
    except (ValueError, AttributeError, UnicodeError):
        enabled = None
    if not isinstance(enabled, bool):
        raise corpus.CorpusError("corpus_metadata", "'enabled' maydoni true/false bo‘lishi kerak.", 400)
    return JSONResponse(auth.set_corpus_submission_access(user_id, enabled), headers=HEADERS)


@router.post("/corpus/documents/{document_id}/reject")
async def reject(request: Request, document_id: str):
    manager = await run_in_threadpool(auth.require_corpus_manager, request)
    await run_in_threadpool(rate_limit.enforce, manager["id"], "corpus")
    body = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4096:
                    raise corpus.CorpusError("corpus_metadata", "So‘rov tanasi juda uzun.", 400)
                body.extend(chunk)
    except TimeoutError:
        raise corpus.CorpusError("upload_interrupted", "So‘rov vaqti tugadi.", 408) from None
    try:
        reason = json.loads(body).get("reason") if body else None
    except (ValueError, AttributeError, UnicodeError):
        reason = None
    return JSONResponse(corpus.reject(document_id, reason), headers=HEADERS)
