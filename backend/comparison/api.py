import asyncio
import hashlib
import json
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from backend import auth, corpus, reports
from backend.persistence import ServiceError

from .matching import tokenize
from .policy import ComparisonError, MAX_BODY_BYTES, UPLOAD_SECONDS
from .runner import run_worker
from .uploads import Uploads

router = APIRouter()
gate = threading.Lock()  # One comparison/upload per backend process; no unbounded queue.


def with_corpus(folder, items):
    """Extract once, retrieve candidates, then compare uploads and corpus together.

    The parser stays in the sandboxed worker and the database stays in this
    process, so the worker never receives credentials.
    """
    extracted = run_worker(folder, {"mode": "extract", "items": items})["documents"]
    document, sources = extracted[0], extracted[1:]
    found, limit = corpus.candidates(tokenize(document["text"]))
    loaded = [doc for doc in (corpus.load_for_comparison(c["id"]) for c in found) if doc]
    (folder / "prepared.json").write_text(
        json.dumps({"document": document, "sources": sources + loaded}, ensure_ascii=False),
        encoding="utf-8")
    result = run_worker(folder, {"mode": "prepared"})
    result["corpus"] = {
        "included": True, "retrieval_policy": corpus.RETRIEVAL_POLICY,
        "fts_configuration": corpus.FTS_CONFIGURATION, "candidate_limit": limit,
        "candidates_compared": len(loaded),
        "note": "Nomzodlar PostgreSQL full-text qidiruvi bilan tanlanadi; bu o‘xshashlik ko‘rsatkichi emas.",
    }
    result["limitations"] = [
        f"Ichki korpusdan faqat {len(loaded)} ta nomzod ({limit} limiti bilan) solishtirildi; "
        "limit tufayli korpusdagi barcha hujjatlar solishtirilmagan.",
        "Korpus manbasidan to‘liq matn ko‘rsatilmaydi; faqat mos parcha va cheklangan kontekst beriladi.",
    ] + result.get("limitations", [])
    return corpus.redact(result)


@router.post("/compare")
async def compare_uploads(request: Request, include_corpus: bool = False):
    headers = {"Cache-Control": "no-store"}
    owner = (await run_in_threadpool(auth.require_user, request))["id"]
    key = reports.request_key(request.headers.get("idempotency-key"))
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
            digest = await run_in_threadpool(reports.fingerprint, folder, items)
            if include_corpus:
                # A corpus run is a different request even with identical files.
                digest = hashlib.sha256(f"{digest}|corpus".encode()).hexdigest()
            previous = await run_in_threadpool(reports.retry, owner, key, digest)
            if previous:
                return JSONResponse(previous, headers=headers)
            # Shield cleanup from client/task cancellation until the owned worker stops.
            work = with_corpus if include_corpus else run_worker
            task = asyncio.create_task(run_in_threadpool(work, folder, items))
            try:
                result = await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                except Exception:
                    pass
                raise
        # Recheck session after expensive work: logout/expiry cannot save a report.
        if (await run_in_threadpool(auth.require_user, request))["id"] != owner:
            raise ServiceError("unauthenticated", "Qayta kiring.", 401)
        result = await run_in_threadpool(reports.save, owner, key, digest, result)
        return JSONResponse(result, headers=headers)
    except ServiceError:
        raise
    except ComparisonError as error:
        return JSONResponse(error.payload(), error.status, headers=headers)
    except (TimeoutError, ClientDisconnect):
        return JSONResponse(ComparisonError("upload_interrupted", "Yuklash uzildi yoki 60 soniya chegarasidan oshdi.", 408).payload(), 408, headers=headers)
    except Exception:
        return JSONResponse(ComparisonError("server_error", "Tekshiruv bajarilmadi. Qayta urinib ko‘ring.", 500).payload(), 500, headers=headers)
    finally:
        gate.release()
