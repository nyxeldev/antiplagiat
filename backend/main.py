from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend import auth
from backend.database import database_ready
from backend.comparison.api import router as comparison_router
from backend.accounts_api import router as accounts_router
from backend.corpus_api import router as corpus_router
from backend.persistence import ServiceError, settings


def require_startup_configuration():
    """Fail fast on an unconfigured/misconfigured process: refuse to start
    serving rather than accept requests that can only ever 503 or run with an
    unreviewed default (docs/decisions.md Sect.14). Raising here stops uvicorn
    from starting at all, with the same descriptive message a request would
    have gotten -- never swallowed, never falls through to a default.
    """
    settings()
    auth.public_origin()


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_startup_configuration()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(comparison_router)
app.include_router(accounts_router)
app.include_router(corpus_router)


@app.exception_handler(ServiceError)
async def service_error(request, error):
    return JSONResponse({"error": {"code": error.code, "message": error.message}},
                        error.status, headers={"Cache-Control": "no-store"})


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse({"error": {"code": "request", "message": "So‘rov parametrlari noto‘g‘ri."}},
                        400, headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    if database_ready():
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "not_ready"}, status_code=503)
