# 0013. Redis-backed rate-limit and idempotency for multi-replica deployment

Date: 2026-06-25
Status: Accepted (supersedes ADR-0007 in production deployments)

## Context

ADR-0007 documented in-memory token-bucket rate limiting and TTL idempotency caching as a Stage 1 simplification. The plan was always to swap them to a shared store before the service goes multi-replica, because:

- Two replicas with in-process token buckets effectively double the rate limit per API key.
- Two replicas with in-process idempotency caches don't deduplicate retries — the second attempt hits a different pod and gets re-executed.

Phase 1 starts the production-readiness work. Redis is the natural target: well-known operationally, atomic primitives suit rate-limit and idempotency patterns, low operational overhead, no schema management.

## Decision

Both `api.ratelimit` and `api.idempotency` modules expose a Protocol-based interface with two implementations behind a settings-driven factory:

- **`REDIS_URL` empty** → in-memory implementations (token bucket, TTL dict). Dev experience unchanged; tests run without external services.
- **`REDIS_URL` set** → Redis implementations (sliding-window counter, JSON-serialized response with TTL). Multi-replica safe.

The dispatch happens once per process at first use; `reset()` drops the singleton so the next call rebuilds from config (used by tests).

### Rate limiter: sliding-window counter, not token bucket

The in-memory implementation uses a real token bucket. The Redis variant uses a sliding-window counter (`INCR redis_key:{minute}` with `EXPIRE 70s`). Differences:

- Token bucket refills continuously; sliding window resets on minute boundaries.
- Token bucket needs a Lua script in Redis to be atomic across the read-modify-write cycle. Sliding window is two primitive commands in a pipeline.
- For our use case (rough per-key throttling, not precise burst control), they're equivalent.

The simpler design wins. If we ever need exact token-bucket semantics distributed, a Lua script lands then.

### Idempotency: JSON serialization

`CorrectResponse` uses Pydantic, so `model_dump_json()` and `model_validate_json()` round-trip cleanly into Redis. Set with `EX=600` matches the in-memory 10-minute TTL semantics.

### Failure mode: fail open

If Redis is unreachable, both implementations log a warning and **fail open**:

- Rate limiter returns `True` (request proceeds without throttling)
- Idempotency cache returns `None` from `get` (treated as miss) and silently swallows `put`

Rationale: rate limiting and idempotency are defensive features. The service's primary job is corrections. If Redis is down, throttling stops working but corrections keep flowing — better than degrading the whole service to 503. Operators see the warning logs and the resulting traffic spike on dashboards and react. A future enhancement could add a metric (`backend_errors_total{component}`) so the failure shows up in Prometheus.

## Consequences

- Single-replica dev workflow is unchanged: `make dev` with empty `REDIS_URL` works exactly as before. All 153 pre-existing tests still pass.
- Multi-replica deployment is now unblocked. `docker-compose.yml` includes a Redis service; the compose `service` automatically points at it via `REDIS_URL=redis://redis:6379/0`.
- The Protocol-based design makes future swaps cheap. A KeyDB or DragonflyDB drop-in would Just Work; a more exotic backend (etcd, Consul) would slot in as a new class.
- `fakeredis` covers Redis behavior in CI without an external service — 10 new contract tests verify both backends.
- ADR-0007 stays accurate for the in-memory dev path; this ADR records the production-deployment behavior.
