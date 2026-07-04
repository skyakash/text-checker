# 0015. MCP server: thin HTTP wrapper with stdio + HTTP transports

Date: 2026-07-04
Status: Accepted

## Context

text-checker needs to be consumable by four kinds of clients without any
of them duplicating correction logic: developer chat panels in VS Code
(Copilot/Codex) and Claude Code, remote bots (Jira, Slack), CI pipelines,
and hand-rolled scripts. The user-facing goal is that a team member can
type "check this release note" into a chat panel and get product-aware
correction with zero per-developer setup.

The Model Context Protocol is the natural glue for the chat-panel case.
But the way we implement the MCP server matters a lot: if the MCP process
imports the correction pipeline and opens the Chroma vector store, we get
two processes fighting over embedded Chroma (a corruption risk), we split
auth/rate-limit/idempotency/metrics between two code paths, and we make
the ADR-0013 Redis integration meaningless for MCP traffic.

The alternative — having the MCP server call `POST /v1/correct` over HTTP
against the running service — sidesteps all of that at the cost of one
extra network hop within the same host.

## Decision

`src/text_checker/mcp_server.py` implements a FastMCP server that is
a **thin HTTP client of the text-checker service**. Every tool call
translates to one or two HTTP requests against the existing REST API.
The pipeline is never imported into the MCP process; the Chroma store
is never opened by the MCP process.

### Tool surface

- `correct_text(text, mode, model?)` → `POST /v1/correct`
- `list_modes()` → `GET /v1/modes`
- `list_models()` → `GET /v1/models` (returns `[{provider, model}]`)
- `ingest_document(content, source, section?)` → `POST /v1/rag/ingest`

`ingest_document` is deliberately part of the surface so an authorised
bot (or a developer via chat) can push new product docs into the shared
RAG store without shell access to the server. This is the same reason
ADR-0016's server-side ingestion endpoint exists.

### Transports

Two are supported:

- **stdio** (default): `text-checker-mcp` — for VS Code Copilot Chat,
  Claude Code, and any local per-user MCP host. FastMCP's built-in
  stdio transport; no auth needed because the client owns the process.
- **HTTP** (streamable): `text-checker-mcp --http` on port 8081 — for
  remote bots and multi-user access.

### HTTP auth: X-API-Key header, fail-closed

The HTTP transport wraps the MCP ASGI app in a Starlette middleware
that requires `X-API-Key`. Two important choices:

1. **Fail-closed**: if the server has no key configured (neither
   `MCP_API_KEY` nor `TEXT_CHECKER_API_KEY`), the middleware returns
   500 on every request instead of silently allowing all traffic.
   Accidentally exposing an unauthenticated MCP endpoint is a much
   worse failure than refusing to serve until the operator sets a key.
2. **`/healthz` is exempt** so orchestrators (docker-compose,
   Kubernetes) can probe the endpoint without needing a secret.

Keys can be different: `MCP_API_KEY` for the MCP transport, `TEXT_CHECKER_API_KEY`
for the upstream service. If only the latter is set, the middleware
uses it — one-key setups just work.

## Consequences

- All guardrails apply uniformly. Rate limits, idempotency, hallucination
  guard, mask-and-restore, RAG grounding — everything flows through
  `/v1/correct`, which means MCP consumers can't accidentally bypass a
  guard the direct HTTP consumers respect.
- No embedded-Chroma corruption risk. Only the main service opens the
  vector store.
- The MCP process is trivially small (~180 lines) and can be scaled or
  restarted independently. It has no persistent state.
- One extra network hop (localhost → localhost) per MCP call. Latency
  cost is negligible against LLM inference time; if it ever becomes
  visible we can Unix-socket it.
- Configuration is simple: `TEXT_CHECKER_URL` (upstream) and
  `TEXT_CHECKER_API_KEY` (upstream key), plus optionally `MCP_API_KEY`
  (if the MCP-facing key differs from upstream).
- Adding tools is a matter of one decorator + one HTTP call. The full
  correction contract stays defined in the OpenAPI schema, not
  duplicated in MCP tool schemas.
- The `ingest_document` tool inherits the service's 200 KB per-request
  content cap (Content-Length middleware in `main.py`, backed by a
  post-parse check in the endpoint). Production deployments should
  also enforce a matching request-body limit at the reverse proxy so
  multi-MB payloads are rejected before the app even sees them.
