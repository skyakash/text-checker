# 0016. Provider-aware model routing with `provider:model` syntax

Date: 2026-07-04
Status: Accepted

## Context

Two related gaps in the model-routing code surfaced when reviewing
against the goal "easy model switching across local, self-hosted, and
cloud providers":

1. **The `model` override was always dispatched to ollama.** Passing
   `model="claude-haiku-4-5"` to `/v1/correct` didn't route to
   Anthropic — it sent that string to ollama, which fails. So the
   registry's Anthropic and OpenAI providers were unreachable from
   client requests; the only way to get to them was via
   `quality_tier=high`, which is coarse.
2. **No way to add a self-hosted or cloud OpenAI-compat endpoint
   without editing code.** vLLM, llama.cpp server, TGI, LM Studio,
   hosted inference APIs — all of these speak the OpenAI shape and
   should slot in without touching `registry.py`.

## Decision

### `provider:model` syntax on the override

`model` accepts `provider:model` syntax and is parsed by splitting on
the **first** colon only:

```
ollama:qwen2.5:7b-instruct    →  ollama,    qwen2.5:7b-instruct
anthropic:claude-haiku-4-5    →  anthropic, claude-haiku-4-5
custom:llama-3.3-70b          →  custom,    llama-3.3-70b
qwen2.5:0.5b                  →  None (bare)
```

The first-colon-only rule matters because ollama tags contain colons —
`ollama:qwen2.5:7b-instruct` must not turn into `provider=ollama,
model=qwen2.5`. A bare model name (no known provider prefix) preserves
the old behavior: route to ollama. So every existing caller passing raw
ollama tags keeps working.

Unknown provider prefixes (`bedrock:...`, `gemini:...`) return HTTP 400
with `unknown_provider` in the detail. Explicit failure beats silent
misrouting.

### Config-driven `custom` provider

Three new settings register a generic OpenAI-compat provider:

- `CUSTOM_BASE_URL` — endpoint like `https://vllm.internal/v1`
- `CUSTOM_API_KEY` — Bearer token if the endpoint needs one
- `CUSTOM_MODEL` — model name to advertise in `/v1/models`

When `CUSTOM_BASE_URL` is set, the registry gains a `custom` provider.
Because it uses `OpenAICompatProvider` (the same class that powers
ollama, anthropic, and openai), it works with anything that speaks the
OpenAI Chat Completions shape — no adapter code required.

### `/v1/models` returns `[{provider, model}]`

Old shape was `["qwen2.5:7b-instruct", "claude-haiku-4-5", ...]` — no way
for a client to know which prefix to use. New shape includes the provider
so clients (VS Code Copilot, CLI, MCP) can round-trip the exact string
back as `provider:model`.

## Consequences

- A single environment change flips the whole team to a different backend:
  set `CUSTOM_BASE_URL` and reference `custom:model-name` in requests.
  Rolling back is a config revert, not a redeploy of new code.
- The registry stays a two-file abstraction (`base.py`, `registry.py` +
  the one `openai_compat.py` implementation). Cloud/self-hosted/local
  variance lives in configuration, not code.
- Backwards compatibility is preserved. All existing tests continued to
  pass unchanged (24 new registry/routing tests were added on top).
- `quality_tier=high` still works: if no override is passed, tier-based
  routing kicks in as before (anthropic → openai → ollama).
- The MCP `list_models()` tool (see ADR-0015) surfaces the new shape
  directly, so Copilot Chat can suggest which prefix to use.
- Follow-on: the eval harness could gain a matrix mode that runs the
  same input across every configured `provider:model` — falls out
  naturally now that the surface is uniform.
