from fastapi import Header, HTTPException

from ..config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    keys = settings.api_keys_set
    if not keys:
        return "anonymous"
    if x_api_key is None or x_api_key not in keys:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    return x_api_key
