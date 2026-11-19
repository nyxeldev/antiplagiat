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
from backend import auth, corpus, rate_limit, reports
from backend.persistence import ServiceError

from .matching import tokenize
from .policy import ComparisonError, MAX_BODY_BYTES, UPLOAD_SECONDS
from .runner import run_worker
from .uploads import Uploads

router = APIRouter()
gate = threading.Lock()  # One comparison/upload per backend process; no unbounded queue.


def with_corpus(folder, items, normalization="v2", user_id=None):
    """Extract once, retrieve candidates, then compare uploads and corpus together.

    The parser stays in the sandboxed worker and the database stays in this
    process, so the worker never receives credentials.

    Rate limited here (scope="compare"), not at the top of compare_uploads(),
    because this is the only /compare path that can ever expose corpus
    excerpts -- a plain two-upload comparison touches no corpus text and is
    already serialized by this module's single-flight `gate` lock. Checked
    before any extraction work starts.

    normalization is one of three modes (docs/decisions.md Sect.5), chosen
    by a reader explicitly ticking an experimental checkbox -- old requests
    keep their exact old behaviour either way:
      "v2"          -- unchanged candidate retrieval, unchanged matching.
      "v3"          -- corpus.candidates() matches through the rule-based
                       uz-latin-v3 suffix stripper instead; matching is
                       still the unchanged exact/shingle algorithm. This is
                       the pre-existing, unchanged "v3" behaviour.
      "v3-matching" -- new. Retrieval is the same as "v3" above, AND the
                       exact/shingle algorithm itself also matches through
                       uz-latin-v3-stemmed keys (backend/comparison/matching.py,
                       match_keys()/morph_key()), so a morphological variant
                       can be found as a match. The highlighted span is
                       always the full original word (offsets untouched);
                       only which runs are FOUND can change.
    See backend/comparison/uz_latin_v3.py and docs/benchmarks/uz-morph-v3*.md
    for what the stripper does and its measured, known limitations.
    """
    rate_limit.enforce(user_id, "compare")
    extracted = run_worker(folder, {"mode": "extract", "items": items})["documents"]
    document, sources = extracted[0], extracted[1:]
    tokens = tokenize(document["text"])
    retrieval_normalization = "v3" if normalization in ("v3", "v3-matching") else "v2"
    kwargs = {"normalization": retrieval_normalization}
    if retrieval_normalization == "v3":
        kwargs["text"] = document["text"]
    found, limit = corpus.candidates(tokens, **kwargs)
    loaded = [doc for doc in (corpus.load_for_comparison(c["id"]) for c in found) if doc]
    (folder / "prepared.json").write_text(
        json.dumps({"document": document, "sources": sources + loaded}, ensure_ascii=False),
        encoding="utf-8")
    manifest = {"mode": "prepared"}
    if normalization == "v3-matching":
        manifest["matching_normalization"] = "uz-latin-v3"
    result = run_worker(folder, manifest)
    result["corpus"] = {
        "included": True, "retrieval_policy": corpus.RETRIEVAL_POLICY,
        "fts_configuration": corpus.FTS_CONFIGURATION, "candidate_limit": limit,
        "candidates_compared": len(loaded), "normalization": normalization,
        "note": "Nomzodlar PostgreSQL full-text qidiruvi bilan tanlanadi; bu o‘xshashlik ko‘rsatkichi emas.",
    }
    result["limitations"] = [
        f"Ichki korpusdan faqat {len(loaded)} ta nomzod ({limit} limiti bilan) solishtirildi; "
        "limit tufayli korpusdagi barcha hujjatlar solishtirilmagan.",
        "Korpus manbasidan to‘liq matn ko‘rsatilmaydi; faqat mos parcha va cheklangan kontekst beriladi.",
    ] + ([
        "Normalizatsiya: uz-latin-v3 (tajriba, qoidaga asoslangan qo‘shimcha-tanish). Faqat nomzod "
        "tanlashga ta’sir qiladi; moslikni belgilash hamon o‘zgarmagan exact/shingle algoritmida.",
    ] if normalization == "v3" else []) + ([
        "Normalizatsiya: uz-latin-v3 + matching (tajriba, qoidaga asoslangan qo‘shimcha-tanish). Nomzod "
        "tanlashga HAM, moslikni belgilashga HAM ta’sir qiladi: morfologik variant (masalan "
        "“kitoblarni”/“kitobni”) endi mos deb belgilanishi mumkin. Highlight hamon ORIGINAL "
        "to‘liq so‘zni (qo‘shimchasi bilan) qamraydi; faqat qaysi so‘zlar mos deb topilishi o‘zgaradi. "
        "Ushbu rejim yolg‘on musbatlar bo‘yicha o‘lchangan, ammo hamon tajriba xususiyatga ega.",
    ] if normalization == "v3-matching" else []) + result.get("limitations", [])
    return corpus.redact(result, user_id)


@router.post("/compare")
async def compare_uploads(request: Request, include_corpus: bool = False, normalization: str = "v2"):
    headers = {"Cache-Control": "no-store"}
    owner = (await run_in_threadpool(auth.require_user, request))["id"]
    key = reports.request_key(request.headers.get("idempotency-key"))
    if not gate.acquire(blocking=False):
        return JSONResponse(ComparisonError("busy", "Boshqa tekshiruv davom etmoqda. Birozdan so‘ng qayta urinib ko‘ring.", 429).payload(), 429, headers=headers)
    try:
        if normalization not in ("v2", "v3", "v3-matching"):
            raise ComparisonError("normalization_invalid", "normalization faqat 'v2', 'v3' yoki 'v3-matching' bo‘lishi mumkin.", 400)
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
            if len(items) < 2 and not include_corpus:
                raise ComparisonError("no_sources", "Kamida bitta manba fayl yuklang yoki ichki korpusni yoqing.", 400)
            digest = await run_in_threadpool(reports.fingerprint, folder, items)
            if include_corpus:
                # A corpus run is a different request even with identical files;
                # normalization is folded in too, so a v2 and a v3 run against the
                # same files never collide under the same idempotency key.
                digest = hashlib.sha256(f"{digest}|corpus|{normalization}".encode()).hexdigest()
            previous = await run_in_threadpool(reports.retry, owner, key, digest)
            if previous:
                return JSONResponse(previous, headers=headers)
            # Shield cleanup from client/task cancellation until the owned worker stops.
            work = (lambda f, i: with_corpus(f, i, normalization, owner)) if include_corpus else run_worker
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
        debits = result.pop("_excerpt_debits", None)
        result = await run_in_threadpool(reports.save, owner, key, digest, result)
        # Only after save() exists do we have a report_id to attach the audit
        # rows to -- redact() ran before the report row existed and could only
        # decide what to debit, not write it (see corpus.py's redact()).
        if debits:
            await run_in_threadpool(corpus.record_excerpt_disclosures, owner, result["report_id"], debits)
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
