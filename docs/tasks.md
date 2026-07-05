# Project Task List

Complete task list for text-checker, updated as work progresses.

**Status key:** ✅ Done · 🔵 Planned · 🟡 Deferred · ⏭ Skipped

---

## Summary

| Status | Count |
|---|---|
| ✅ Done | 30 |
| 🔵 Planned | 0 |
| 🟡 Deferred | 9 |
| ⏭ Skipped / Superseded | 2 |

Implementation notes for the completed MCP/integrations batch: [plan-mcp-and-integrations.md](plan-mcp-and-integrations.md)

---

## Stage 1 — Core service & pipeline

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Phase 0 decisions | ✅ Done | Provider abstraction, pipeline design, stack choices confirmed |
| 2 | Align working directory with repo | ✅ Done | Local git set up, connected to GitHub remote |
| 3 | Scaffold project skeleton | ✅ Done | pyproject.toml, src layout, Dockerfile, docker-compose |
| 4 | Architecture doc with Mermaid diagram | ✅ Done | docs/architecture.md |
| 5 | Provider abstraction | ✅ Done | OpenAI-compat HTTP layer — Ollama, vLLM, llama.cpp, Anthropic, OpenAI |
| 6 | Correction pipeline | ✅ Done | Preprocess → prompts → LLM → postprocess; hallucination guard; edit-ratio |
| 7 | FastAPI service & endpoints | ✅ Done | /v1/correct, /v1/modes, /v1/models, /healthz, /readyz, /metrics; auth; rate-limit; idempotency |
| 8 | Observability | ✅ Done | Prometheus counters + histograms, structlog JSON logs, Grafana in compose |
| 9 | Tests | ✅ Done | 75 unit + contract tests, 2 integration tests (auto-skip without Ollama) |
| 10 | Docker-compose + run instructions | ✅ Done | Multi-stage Dockerfile, compose with Ollama + Prometheus + Grafana |
| 11 | Fix hallucination guard + model output visibility | ✅ Done | Guard detects dropped tokens; edit-ratio 0.30→0.45; model_output in flagged response |

---

## Stage 2 — Glossary & RAG

| # | Task | Status | Notes |
|---|---|---|---|
| 12 | Glossary store + CLI + masker integration | ✅ Done | JSON-backed protected-term store; case-insensitive mask/restore; CLI: list/add/remove/import/reset |
| 13 | RAG ingestion + retrieval + orchestrator | ✅ Done | Chroma vector store; nomic-embed-text embeddings; multi-format loaders; top-k prompt injection |
| 14 | LLM-based glossary extractor | ✅ Done | Extract candidate terms from product docs; --add flag to merge; ADR-0010 |
| 15 | Glossary + RAG documentation | ✅ Done | README, ADR-0009, ADR-0010, architecture updated |
| 16 | Tighten RAG defaults | ✅ Done | min_score 0.65→0.50; skip grammar mode; ADR-0011 |
| 17 | RAG retrieval score histogram (Prometheus) | ✅ Done | Fine-grained buckets 0.4–0.8; per-mode label; operators can calibrate threshold from traffic |
| 18 | Linux / RHEL + proxy deployment docs | ✅ Done | Bare-metal systemd path, HTTPS_PROXY env, prerequisite install instructions |
| 19 | Fix glossary + RAG interaction | ✅ Done | Reapply glossary masks in RAG chunks; canonicalize case in model output; ADR-0012 |

---

## Phase 1 — Production readiness

| # | Task | Status | Notes |
|---|---|---|---|
| 20 | Redis-backed rate-limit + idempotency | ✅ Done | Sliding-window INCR/EXPIRE; JSON-serialised cache; fail-open; fakeredis tests; ADR-0013 |
| 21 | Postgres request log | 🟡 Deferred | Feeds Phase 2 eval flywheel; not needed for single-replica; blocked on pgvector decision |
| 22 | Active provider probe on /readyz | ✅ Done | Probes Ollama + Redis with 5s cache; returns 200/503; ADR-0014 |
| 23 | Helm chart in deploy/k8s/ | 🟡 Deferred | No Kubernetes today; Docker Compose is the production target |
| 24 | pgvector swap for RAG store | 🟡 Deferred | Blocked on Postgres (#21); Chroma serves current needs |
| 25 | Production deployment recipe (single-replica) | ✅ Done | docker-compose.prod.yml overlay; systemd unit; backup.sh + update.sh; ADR-0014 |
| — | OpenTelemetry traces | ⏭ Skipped | No tracing backend available; Prometheus + structlog covers current needs |

---

## MCP Server & integrations

Implementation order and full specs: [plan-mcp-and-integrations.md](plan-mcp-and-integrations.md). Build #31 and #32 first — #26 depends on both.

| # | Task | Status | Notes |
|---|---|---|---|
| 31 | Provider-aware model routing | ✅ Done | `provider:model` override syntax (first-colon split for ollama tags); config-driven `custom` provider for any OpenAI-compat endpoint; unknown-provider returns 400; ADR-0016 |
| 32 | Server-side RAG ingestion API | ✅ Done | POST /v1/rag/ingest, GET /v1/rag/sources, DELETE /v1/rag/sources/{source}; CLI `--server` mode for remote ingest; 200KB per-request cap |
| 26 | MCP server core | ✅ Done | FastMCP thin wrapper over HTTP API; correct_text, list_modes, list_models, ingest_document; stdio + HTTP transports; fail-closed API-key auth on HTTP; ADR-0015 |
| 27 | VS Code / Copilot Chat linter integration | ✅ Done | .vscode/mcp.json committed to repo; both HTTP (recommended) and stdio config shown; secret via VS Code input prompt |
| 33 | CI client CLI for pipelines | ✅ Done | `text-checker-check` script with exit codes 0/1/2; --json + --diff outputs; reference GitHub Actions workflow at deploy/github-actions/lint-release-notes.yml |
| 28 | Jira Bot integration | ✅ Done | docs/integrations/jira-bot.md — webhook → bot → HTTP or MCP bridge with Python example; security notes; both HTTP-API and MCP paths documented |
| 30 | ADRs + docs sweep | ✅ Done | ADR-0015 + ADR-0016 written and indexed; concepts.md updated; README updated |
| ~~29~~ | ~~GitHub Actions via raw curl~~ | ⏭ Superseded | Folded into #33 — the client CLI is the supported pipeline path |
| 40 | Env-driven main HTTP bind (`SERVICE_HOST`/`SERVICE_PORT`) | ✅ Done | Env vars honored by Makefile, Dockerfile (with signal-safe exec CMD), systemd unit, and docker-compose (both container bind and host publish, plus `SERVICE_PUBLISH_PORT` for split-port cases). MCP compose service `TEXT_CHECKER_URL` tracks `SERVICE_PORT` so the MCP → main hop follows moves. Live-verified on port 9090. README "Restricted environments / custom ports" section documents recipes. |

---

## Phase 2–4 — Future roadmap

| # | Task | Status | Notes |
|---|---|---|---|
| P2 | Quality flywheel — eval metrics + /v1/feedback | 🟡 Deferred | GLEU, ERRANT F0.5, BERTScore, LLM-judge; per-model Grafana scorecard; A/B routing |
| P2 | Per-tenant isolation (glossary + RAG) | 🟡 Deferred | Stage 2 ships single global stores; per-tenant needed for multi-team use |
| P3 | Critic-reviser loop (quality_tier=high) | 🟡 Deferred | Bounded writer → critic → reviser; max one revision; structured JSON critic output |
| P3 | Sentence-aware chunker for long inputs | 🟡 Deferred | Stage 1 rejects >5000 chars with 413; chunker needed for long docs (ADR-0008) |
| P4 | Example RAG (few-shot from approved corrections) | 🟡 Deferred | Teaches voice from past human-approved edits; needs labeled dataset that doesn't exist yet |
| P4 | Per-tenant LoRA fine-tuning | 🟡 Deferred | Gated by eval harness from Phase 2; requires labeled correction dataset |
