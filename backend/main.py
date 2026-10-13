from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.database import database_ready
from backend.comparison.api import router as comparison_router
from backend.accounts_api import router as accounts_router
from backend.corpus_api import router as corpus_router
from backend.persistence import ServiceError


app = FastAPI()
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
