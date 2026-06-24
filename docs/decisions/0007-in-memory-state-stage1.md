# 0007. In-memory rate-limit and idempotency for Stage 1

Date: 2026-06-17
Status: Accepted

## Context

The service has three stateful concerns:

- **Rate limiting** per API key (currently 60 req/min, token-bucket)
- **Idempotency** — replay the cached response when the same `Idempotency-Key` arrives within 10 minutes
- **API-key validation** (this is config, not state)

A multi-replica deployment in Kubernetes needs these in a shared store. Two replicas with in-process token buckets effectively double the rate limit; two replicas with in-process idempotency caches will fail to deduplicate when retries hit different pods.

Two paths:

1. Build Redis-backed implementations from day 1.
2. Build in-memory implementations for Stage 1; commit to swapping for Redis as the first Phase 1 task before multi-replica deployment.

## Decision

We will use in-memory implementations for Stage 1. Both the token bucket (`api/ratelimit.py`) and the idempotency cache (`api/idempotency.py`) are simple in-process data structures with no external dependency. The Phase 1 roadmap explicitly schedules the Redis swap as the first task before any multi-replica deployment.

## Consequences

- Local dev and single-replica deploy work with no infrastructure beyond Python and Ollama.
- Tests are simpler: no Redis fake needed.
- Multi-replica deployment is **blocked** until the Redis swap lands. This is recorded in `docs/architecture.md` and ADR readers see this explicitly.
- The interfaces (`enforce_rate_limit` dependency, `IdempotencyCache.get/put`) are designed so the swap is a class-replacement, not a behavior change.
- A `REDIS_URL` env var is reserved in `.env.example` so deployment configs can be prepared ahead of the swap.
