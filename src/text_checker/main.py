import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from . import readiness
from .api.rag_routes import router as rag_router
from .api.routes import router
from .api.schemas import RAG_INGEST_MAX_BYTES
from .config import settings
from .observability.logging import configure_logging, get_logger
from .observability.metrics import metrics_app

# A little headroom over RAG_INGEST_MAX_BYTES (200 KB) — Pydantic's JSON
# wrapping and header overhead means the raw Content-Length is a bit
# larger than the content payload. The endpoint's post-parse check is
# the authoritative backstop; this is an early cutoff to avoid reading
# multi-MB bodies before rejecting them.
_INGEST_CONTENT_LENGTH_LIMIT = RAG_INGEST_MAX_BYTES + 50_000

configure_logging(settings.log_level)
log = get_logger()

app = FastAPI(title="text-checker", version="0.1.0")
app.include_router(router, prefix="/v1")
app.include_router(rag_router, prefix="/v1/rag")
app.mount("/metrics", metrics_app)

_LOG_SKIP_PATHS = {"/metrics", "/healthz", "/readyz"}


@app.middleware("http")
async def reject_oversized_ingest(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    # Reject huge POSTs to /v1/rag/ingest BEFORE the body is read into
    # memory. Without this, uvicorn's default (no cap) means a caller
    # sending a 500 MB body wastes network + memory before the endpoint's
    # RAG_INGEST_MAX_BYTES check fires post-parse. Clients can omit or
    # lie about Content-Length; the post-parse check remains as backstop.
    if request.method == "POST" and request.url.path == "/v1/rag/ingest":
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > _INGEST_CONTENT_LENGTH_LIMIT:
            return JSONResponse(
                {
                    "detail": (
                        f"request body exceeds {_INGEST_CONTENT_LENGTH_LIMIT} bytes; "
                        f"content field cap is {RAG_INGEST_MAX_BYTES} bytes — split the document"
                    )
                },
                status_code=413,
            )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    if request.url.path not in _LOG_SKIP_PATHS:
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> JSONResponse:
    report = await readiness.check()
    return JSONResponse(
        content={
            "status": "ready" if report.ready else "not ready",
            "components": report.components,
        },
        status_code=200 if report.ready else 503,
    )
