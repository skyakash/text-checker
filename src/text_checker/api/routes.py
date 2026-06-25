import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..observability.metrics import latency_seconds, requests_total
from ..pipeline import orchestrator
from ..pipeline.exceptions import InputTooLongError, NonEnglishInputError
from ..providers.registry import get_registry
from .idempotency import IdempotencyCache, get_cache, idempotency_header
from .ratelimit import enforce_rate_limit
from .schemas import CorrectRequest, CorrectResponse, Mode

router = APIRouter()


@router.post("/correct", response_model=CorrectResponse)
async def correct(
    req: CorrectRequest,
    _key: str = Depends(enforce_rate_limit),
    idem_key: str | None = Depends(idempotency_header),
    cache: IdempotencyCache = Depends(get_cache),
) -> CorrectResponse:
    if idem_key:
        cached = await cache.get(idem_key)
        if cached is not None:
            return cached

    try:
        resp = await orchestrator.run(req, get_registry())
    except NonEnglishInputError as e:
        requests_total.labels(mode=req.mode.value, model="n/a", status="rejected_lang").inc()
        raise HTTPException(status_code=422, detail=str(e)) from e
    except InputTooLongError as e:
        requests_total.labels(mode=req.mode.value, model="n/a", status="rejected_size").inc()
        raise HTTPException(status_code=413, detail=str(e)) from e
    except httpx.HTTPError as e:
        requests_total.labels(mode=req.mode.value, model="n/a", status="upstream_error").inc()
        raise HTTPException(status_code=502, detail=f"upstream provider error: {e}") from e

    status = "flagged" if resp.flagged else "ok"
    requests_total.labels(mode=req.mode.value, model=resp.model_used, status=status).inc()
    latency_seconds.labels(mode=req.mode.value, model=resp.model_used).observe(
        resp.metrics.latency_ms / 1000.0
    )

    if idem_key:
        await cache.put(idem_key, resp)
    return resp


@router.get("/modes")
async def modes() -> list[str]:
    return [m.value for m in Mode]


@router.get("/models")
async def models() -> list[str]:
    return get_registry().available_models()
