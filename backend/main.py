from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.database import database_ready
from backend.comparison.api import router as comparison_router


app = FastAPI()
app.include_router(comparison_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    if database_ready():
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "not_ready"}, status_code=503)
