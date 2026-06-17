from fastapi import FastAPI

from .api.routes import router
from .observability.metrics import metrics_app

app = FastAPI(title="text-corrector", version="0.1.0")
app.include_router(router, prefix="/v1")
app.mount("/metrics", metrics_app)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
