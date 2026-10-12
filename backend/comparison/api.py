import asyncio
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from .policy import ComparisonError, MAX_BODY_BYTES, UPLOAD_SECONDS
from .runner import run_worker
from .uploads import Uploads

router = APIRouter()
gate = threading.Lock()  # One comparison/upload per backend process; no unbounded queue.


@router.post("/compare")
async def compare_uploads(request: Request):
    headers = {"Cache-Control": "no-store"}
    if (request.url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or not request.client or request.client.host not in {"127.0.0.1", "::1"}
            or request.headers.get("x-antiplagiat-local") != "1"):
        return JSONResponse(ComparisonError("local_only", "Faqat lokal interfeys orqali foydalaning.", 403).payload(), 403, headers=headers)
    if not gate.acquire(blocking=False):
        return JSONResponse(ComparisonError("busy", "Boshqa tekshiruv davom etmoqda. Birozdan so‘ng qayta urinib ko‘ring.", 429).payload(), 429, headers=headers)
    try:
        length = request.headers.get("content-length")
        if length and (not length.isdecimal() or int(length) > MAX_BODY_BYTES):
            raise ComparisonError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
        with tempfile.TemporaryDirectory(prefix="antiplagiat-") as directory:
            folder = Path(directory)
            upload = Uploads(folder, request.headers.get("content-type", ""))
            try:
                async with asyncio.timeout(UPLOAD_SECONDS):
                    async for chunk in request.stream():
                        upload.write(chunk)
                items = upload.finish()
            except (ComparisonError, TimeoutError, ClientDisconnect):
                raise
            except Exception:
                raise ComparisonError("upload_format", "Yuklash formati buzilgan.", 400) from None
            finally:
                upload.close()
            # Shield cleanup from client/task cancellation until the owned worker stops.
            task = asyncio.create_task(run_in_threadpool(run_worker, folder, items))
            try:
                result = await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                except Exception:
                    pass
                raise
        return JSONResponse(result, headers=headers)
    except ComparisonError as error:
        return JSONResponse(error.payload(), error.status, headers=headers)
    except (TimeoutError, ClientDisconnect):
        return JSONResponse(ComparisonError("upload_interrupted", "Yuklash uzildi yoki 60 soniya chegarasidan oshdi.", 408).payload(), 408, headers=headers)
    except Exception:
        return JSONResponse(ComparisonError("server_error", "Tekshiruv bajarilmadi. Qayta urinib ko‘ring.", 500).payload(), 500, headers=headers)
    finally:
        gate.release()
