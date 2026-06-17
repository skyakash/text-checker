import httpx
from fastapi import APIRouter, HTTPException

from ..pipeline import orchestrator
from ..pipeline.exceptions import InputTooLongError, NonEnglishInputError
from ..providers.registry import get_registry
from .schemas import CorrectRequest, CorrectResponse, Mode

router = APIRouter()


@router.post("/correct", response_model=CorrectResponse)
async def correct(req: CorrectRequest) -> CorrectResponse:
    try:
        return await orchestrator.run(req, get_registry())
    except NonEnglishInputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except InputTooLongError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream provider error: {e}") from e


@router.get("/modes")
async def modes() -> list[str]:
    return [m.value for m in Mode]


@router.get("/models")
async def models() -> list[str]:
    return get_registry().available_models()
