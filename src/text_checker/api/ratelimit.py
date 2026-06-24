import time
from collections import defaultdict
from threading import Lock

from fastapi import Depends, HTTPException

from .auth import require_api_key

RATE_LIMIT_PER_MINUTE = 60


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill = refill_per_second
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = Lock()

    def try_consume(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


def _new_bucket() -> TokenBucket:
    return TokenBucket(
        capacity=RATE_LIMIT_PER_MINUTE,
        refill_per_second=RATE_LIMIT_PER_MINUTE / 60.0,
    )


_buckets: dict[str, TokenBucket] = defaultdict(_new_bucket)


def reset() -> None:
    _buckets.clear()


def enforce_rate_limit(key: str = Depends(require_api_key)) -> str:
    if not _buckets[key].try_consume():
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    return key
