from fastapi import APIRouter, HTTPException

from .schemas import CorrectRequest, CorrectResponse, Mode

router = APIRouter()


@router.post("/correct", response_model=CorrectResponse)
async def correct(req: CorrectRequest) -> CorrectResponse:
    raise HTTPException(status_code=501, detail="correction pipeline not yet implemented")


@router.get("/modes")
async def modes() -> list[str]:
    return [m.value for m in Mode]


@router.get("/models")
async def models() -> list[str]:
    return []
