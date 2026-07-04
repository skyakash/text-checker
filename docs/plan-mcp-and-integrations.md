# Implementation Plan: MCP Server, Integrations, Model Routing

Status: **Implemented** (2026-07-04) — kept as implementation record. Follow-up fixes from architect review land on 2026-07-05 (see commits after `13ced90`). See [docs/tasks.md](tasks.md) for current status.
Audience: the implementing session (Claude Opus). Everything needed is in this file, `docs/tasks.md`, and the ADRs — no prior conversation context required.

## Goal

Make text-checker consumable by four kinds of clients, without duplicating any correction logic:

1. **VS Code developers** — via MCP, from the Copilot/Codex chat panel
2. **Bots (e.g. Jira)** — via MCP over HTTP, or the plain HTTP API
3. **CI pipelines** — via a client CLI with exit codes (automated release-note linting)
4. **Operators** — remote RAG ingestion against a running server, easy model switching across local/self-hosted/cloud providers

## Architecture principle (do not violate)

All consumers go through the same `POST /v1/correct` pipeline (mask → RAG → LLM → unmask → hallucination guard). The MCP server and CLI are **thin clients of the HTTP API** — they never import the pipeline directly. This keeps auth, rate limiting, idempotency, metrics, and guardrails applying uniformly, and avoids two processes opening the embedded Chroma store (a corruption risk).

## Current-state facts the implementer needs

- Provider abstraction: `src/text_checker/providers/` — `OpenAICompatProvider` + `ProviderRegistry` (ollama always; anthropic/openai when API keys set). **Known limitation:** `registry.route()` sends any `model` override to ollama unconditionally (registry.py line ~49).
- RAG CLI (`python -m text_checker.rag ingest|list|search|remove|reset`) writes **directly to local Chroma files** at `./data/rag/` — it cannot ingest into a running server, and concurrent embedded-Chroma access from two processes is unsafe.
- Auth: `X-API-Key` header, keys from `API_KEYS` env (comma-separated). Rate limit 60/min/key. Idempotency via `Idempotency-Key` header, 10-min TTL, Redis-backed when `REDIS_URL` set.
- Request schema: `text, mode (grammar|style|jira-story|release-note), model, quality_tier (fast|balanced|high), use_rag, idempotency_key`.
- Response schema: `request_id, corrected_text, diff, model_used, flagged, flag_reason, model_output, rag_context_used, metrics`.
- Tests: pytest, ~150 passing; respx for HTTP mocking; fakeredis for Redis. Follow existing conventions in `tests/`.

---

## Task 31 — Provider-aware model routing (do this FIRST — others build on it)

**Problem:** `model="claude-haiku-4-5"` routes to ollama and fails. No way to add a self-hosted vLLM/llama.cpp endpoint without code changes.

**Design:**
- `model` accepts `provider:model` syntax: `"anthropic:claude-haiku-4-5"`, `"custom:llama-3.3-70b"`, `"ollama:qwen2.5:14b-instruct"` (split on **first** colon only — ollama tags contain colons). Bare model name (no known provider prefix) → ollama, preserving backwards compatibility.
- New settings for one generic self-hosted provider: `custom_base_url: str | None`, `custom_api_key: str | None`, `custom_model: str | None`. When `custom_base_url` is set, registry registers provider `"custom"` (OpenAICompatProvider — covers vLLM, llama.cpp server, TGI, any OpenAI-compat endpoint, hosted anywhere).
- `route()` change: parse override prefix → route to that provider (404-style error `unknown_provider` if not registered). `available_models()` includes custom model when configured.
- `/v1/models` response gains `provider` field per model.

**Acceptance:** unit tests for prefix parsing (incl. ollama double-colon tags), routing to each provider, unknown-provider error; ADR-0016 recording the `provider:model` syntax decision.

## Task 32 — Server-side RAG ingestion API (unblocks MCP `ingest_document` and remote CLI)

**Endpoints** (all under existing API-key auth):
- `POST /v1/rag/ingest` — body `{content: str, source: str, section: str | None}`; chunks + embeds + upserts via existing `rag.ingest` machinery; same re-ingest semantics as CLI (same `source` replaces prior chunks). Returns `{source, chunks_indexed}`.
- `GET /v1/rag/sources` — list sources with chunk counts.
- `DELETE /v1/rag/sources/{source}` — remove a source.

**CLI:** `python -m text_checker.rag ingest ... --server http://host:8080 --api-key ...` (or env `TEXT_CHECKER_URL` / `TEXT_CHECKER_API_KEY`) sends files through the API instead of writing local files. Local mode stays the default for dev.

**Guardrail:** per-request content cap (reuse 5000-char pipeline limit? No — ingestion legitimately takes bigger docs; cap at 200KB/request). Note in docs: ingestion endpoint is for trusted operators/bots; it mutates shared team knowledge.

**Acceptance:** contract tests for the three endpoints; CLI `--server` mode test with respx; README + concepts.md updated.

## Task 26 (revised) — MCP server core

`src/text_checker/mcp_server.py` using the official `mcp` python SDK (FastMCP). Thin HTTP client to the service (httpx), base URL + API key from env (`TEXT_CHECKER_URL`, `TEXT_CHECKER_API_KEY`).

**Tools:**
- `correct_text(text, mode="grammar", model=None)` → corrected_text, diff summary, flagged/flag_reason, rag_context_used
- `list_modes()` → modes with descriptions
- `list_models()` → models with providers (from Task 31)
- `ingest_document(content, source)` → chunks_indexed (calls Task 32 endpoint)

**Transports:** stdio (default; for VS Code/Claude Code local) and streamable HTTP on port 8081 (`text-checker-mcp --http`) for bots/remote.
**Auth:** HTTP transport requires the same `X-API-Key` (validate before proxying; never run the MCP HTTP port as an unauthenticated bypass).
**Packaging:** console script `text-checker-mcp` in pyproject; add `mcp` dependency; docker-compose optional service (profile `mcp`).
**Acceptance:** unit tests with respx mocking the API; ADR-0015.

## Task 27 (revised) — VS Code integration

`.vscode/mcp.json` committed (HTTP type pointing at shared server; document stdio alternative). README section "Use from VS Code Copilot Chat" with the three worked examples already in `docs/concepts.md`. Verify end-to-end against a live server before marking done (per project rule: unit tests passing ≠ works).

## Task 33 (new) — CI client CLI for pipelines

`python -m text_checker.check` (console script `text-checker-check`):
- `text-checker-check file.md --mode release-note [--fail-on-flagged] [--diff]`
- stdin support (`-`), multiple files, `--server`/`--api-key` from flags or env
- Exit codes: 0 clean, 1 flagged (when `--fail-on-flagged`), 2 usage/connection error
- Output: human diff by default, `--json` for machines

**Reference workflow** `deploy/github-actions/lint-release-notes.yml`: on PR, run the CLI against changed `release-notes/**.md` files; post corrected diff as PR comment when flagged. (Replaces old task 29's curl approach — the CLI is the supported path.)

## Task 28 (unchanged) — Jira bot integration doc

`docs/integrations/jira-bot.md`: webhook → bot → MCP HTTP (or plain API) → post corrected text as comment. Document, don't build the bot (no Jira instance available here).

## Task 30 (expanded) — ADRs + docs sweep

ADR-0015 (MCP server: thin wrapper, transports, auth), ADR-0016 (provider:model routing + custom provider), ADR index, tasks.md status flips, concepts.md/README updates, architecture.md gains the MCP/CLI consumers.

---

## Implementation order & effort

| Order | Task | Size | Depends on |
|---|---|---|---|
| 1 | #31 model routing | S | — |
| 2 | #32 RAG ingestion API + remote CLI | M | — |
| 3 | #26 MCP server core | M | #31, #32 |
| 4 | #33 CI client CLI + workflow | S | — (better after #31) |
| 5 | #27 VS Code integration | S | #26 |
| 6 | #28 Jira doc, #30 ADRs/docs | S | #26 |

## Definition of done (whole plan)

- All new code covered by unit/contract tests; full suite green.
- **Live verification** against running Ollama: one request per provider path (ollama default, `provider:model` override), one remote ingest, one MCP `correct_text` via stdio, one CI CLI run with a deliberately flagged input.
- docs/tasks.md statuses updated; ADRs 0015/0016 merged; pushed to main.
