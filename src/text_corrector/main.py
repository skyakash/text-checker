import time

from fastapi import FastAPI, Request
from fastapi.responses import Response

from .api.routes import router
from .config import settings
from .observability.logging import configure_logging, get_logger
from .observability.metrics import metrics_app

configure_logging(settings.log_level)
log = get_logger()

app = FastAPI(title="text-corrector", version="0.1.0")
app.include_router(router, prefix="/v1")
app.mount("/metrics", metrics_app)

_LOG_SKIP_PATHS = {"/metrics", "/healthz", "/readyz"}


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
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
