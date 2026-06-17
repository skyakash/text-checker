import httpx
from fastapi import APIRouter, Depends, HTTPException

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
        cached = cache.get(idem_key)
        if cached is not None:
            return cached

    try:
        resp = await orchestrator.run(req, get_registry())
    except NonEnglishInputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except InputTooLongError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream provider error: {e}") from e

    if idem_key:
        cache.put(idem_key, resp)
    return resp


@router.get("/modes")
async def modes() -> list[str]:
    return [m.value for m in Mode]


@router.get("/models")
async def models() -> list[str]:
    return get_registry().available_models()
