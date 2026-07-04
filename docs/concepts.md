# Concepts: LLM, RAG, and MCP

A short reference for the three foundational concepts behind text-checker — what each one is, why it exists, and how they fit together in this project.

![RAG, MCP and LLM overview](images/rag-mcp-llm-overview.png)

---

## LLM — the brain

A **Large Language Model** is a neural network trained on massive amounts of text. Given everything it was trained on plus whatever you put in the prompt, it predicts the most likely next token (word fragment). Repeat that prediction many times and you get a coherent response.

Key constraints:
- **No memory between calls** — each request is independent; the model has no recollection of previous requests.
- **No live data access** — it knows only what was in its training corpus, which has a cutoff date.
- **No knowledge of your private docs** — it has never seen your style guide, product terminology, or internal naming conventions.
- **Can hallucinate** — it generates plausible-sounding text even when it doesn't actually know the answer.

**In text-checker:** [Ollama](https://ollama.ai) runs the model locally (default: `qwen2.5:7b`). The pipeline sends a structured prompt and the model returns corrected text. The hallucination guard and edit-ratio check exist precisely because the LLM can get things wrong.

---

## RAG — giving the LLM a reference book

**Retrieval-Augmented Generation** solves the "LLM doesn't know your private docs" problem without fine-tuning the model. It works in two phases:

### Phase 1 — Ingest (offline, one-time or periodic)

```
Your docs (PDFs, markdown, plain text)
   ↓
Split into overlapping chunks (~500 tokens each)
   ↓
Each chunk → embedding model → vector (list of ~1536 numbers capturing meaning)
   ↓
Stored in a vector database (Chroma in text-checker, at ./data/rag/)
```

This is called **ingestion** (also called indexing or training the RAG). You run it once when your docs change.

```bash
python -m text_checker.rag.cli ingest path/to/your/docs/
```

### Phase 2 — Retrieve + Augment (per request, automatic)

```
User's input text
   ↓
Same embedding model → vector
   ↓
Vector similarity search against the store → top-k most relevant chunks
   ↓
Chunks injected into the LLM prompt alongside the user's text
   ↓
LLM now "knows" your product docs for this request
```

The LLM never sees your whole document library — only the 3–5 chunks most relevant to the current input. This keeps the prompt short and the answer focused.

### Why RAG instead of fine-tuning?

| | RAG | Fine-tuning |
|---|---|---|
| Update docs | Re-ingest (minutes) | Retrain (hours/days, expensive) |
| Explainability | You can see which chunks were used | Opaque |
| Cost | Cheap — just a vector search | Expensive GPU compute |
| Best for | Factual grounding, up-to-date knowledge | Changing the model's style or behavior |

**In text-checker:** RAG is active for `release-note` and `style` modes (skipped for `grammar` — grammar is language-universal, no product context needed). The retrieved chunks ground the model in your product's specific terminology, so it doesn't invent names or rewrite technical terms.

Relevance is measured by a similarity score (0–1). Only chunks scoring above `RAG_MIN_SCORE` (default `0.50`) are injected. You can tune this threshold based on the `rag_retrieval_score` Prometheus histogram.

---

## MCP — a standard way to give an LLM hands

**Model Context Protocol** (open standard by Anthropic) defines a common interface between an LLM host and external capabilities. Instead of every integration being bespoke HTTP glue code, MCP standardizes it:

```
LLM host (Claude Code, Claude API agent)
   ↓  discovers tools via MCP
MCP Server  (exposes: name, description, input schema)
   ↓  executes the actual work
Your service / database / API
```

The LLM decides when to call a tool based on its name and description. The host executes the call, gets a structured result back, and the LLM incorporates it into its response. Think of it like USB-C: one standard plug, many devices.

MCP servers communicate over JSON-RPC, either via stdio (local processes) or HTTP (remote services).

### MCP vs RAG

| | RAG | MCP |
|---|---|---|
| What it provides | Static knowledge (documents) | Dynamic actions (tool calls) |
| When it runs | Before the LLM generates | During LLM generation (on demand) |
| Examples | Style guide chunks, product docs | Search, database lookup, API calls |
| LLM awareness | LLM sees context in prompt | LLM actively chooses to call the tool |

**RAG = reference book. MCP = phone the LLM can pick up and call someone.**

### MCP in text-checker

text-checker ships an MCP server as of ADR-0015. It's a thin HTTP client of the running text-checker service that exposes four tools — `correct_text`, `list_modes`, `list_models`, `ingest_document` — over both stdio (for VS Code Copilot Chat and Claude Code) and streamable HTTP on port 8081 (for remote bots). The HTTP transport requires the same `X-API-Key` the main service does; if no key is configured, the server fails closed rather than silently allowing traffic.

> **Scope.** text-checker only implements the **MCP server** side. It does not consume any other MCP servers — the correction pipeline is deterministic (ADR-0003) and does not perform tool-use loops. If you're looking for an LLM that can call MCP tools during reasoning, that's a different product shape than this one.

Start it locally:

```bash
# stdio (for VS Code — the client owns the process)
text-checker-mcp

# HTTP (for shared team access)
MCP_API_KEY=my-key text-checker-mcp --http
```

Or via docker-compose profile:

```bash
docker compose --profile mcp up -d
```

See [ADR-0015](decisions/0015-mcp-server.md) for the design rationale and [Jira bot integration](integrations/jira-bot.md) for a worked webhook example.

#### text-checker as an MCP hub

```
                        ┌─────────────────────────────────┐
                        │     text-checker MCP server      │
                        │                                  │
   Claude Code ─stdio──▶│  correct_text(text, mode)       │
                        │  list_modes()                    │──▶ /v1/correct (HTTP)
   Jira Bot ───HTTP────▶│  ingest_document(content, src)  │
                        │                                  │──▶ RAG ingest pipeline
   GitHub Action ─HTTP─▶│                                  │
                        └─────────────────────────────────┘
                                      │
                              All guardrails apply:
                              mask → RAG → LLM → guard
```

The MCP server is a thin wrapper over the existing HTTP API. All pipeline guardrails — masking, hallucination guard, edit-ratio — run as normal. MCP just provides the standard plug.

#### Integration scenario 1 — Claude Code / IDE linter

A developer writes a release note in their editor. They ask Claude Code: *"check this release note"*. Claude Code calls `correct_text(text, "release-note")` via the MCP server and surfaces the corrected text and diff inline — same as a spell-checker, but domain-aware with product RAG context.

```
Developer types release note
        ↓
Claude Code (MCP client)
        ↓  correct_text("Fix for PROJ-123...", "release-note")
text-checker MCP server (stdio)
        ↓  POST /v1/correct
text-checker pipeline (mask → RAG → LLM → guard)
        ↓  { corrected, changes, warning }
Claude Code shows inline diff
```

Config: one entry in `.claude/settings.json`:
```json
{
  "mcpServers": {
    "text-checker": {
      "command": "text-checker-mcp",
      "args": ["--api-url", "http://localhost:8080"]
    }
  }
}
```

#### Integration scenario 2 — Jira Bot

When a Jira ticket transitions to **"Ready for Release"**, a webhook fires. The bot calls `correct_text(description, "release-note")` and posts the cleaned version as a comment, or auto-updates the description field.

```
Jira ticket → "Ready for Release"
        ↓  webhook POST
Jira Bot (Python / Node)
        ↓  MCP tool call: correct_text(ticket.description, "release-note")
text-checker MCP server (HTTP transport)
        ↓  pipeline runs
        ↓  { corrected, changes }
Jira Bot → POST comment with corrected text
        or → PATCH ticket description
```

Value: release notes are consistent and style-guide-compliant before they ever reach the release manager, with zero manual effort.

#### Integration scenario 3 — GitHub Actions CI linter

On every pull request, a GitHub Actions workflow calls text-checker to lint the PR description and commit messages. If the service returns `warning: true`, the check fails and the diff is posted as a review comment.

```
PR opened / updated
        ↓  trigger: pull_request
GitHub Actions runner
        ↓  curl POST /v1/correct  { text: pr.body, mode: "style" }
text-checker HTTP API
        ↓  { corrected, changes, warning }
        if warning → gh pr review --comment (posts diff)
        if warning → exit 1 (blocks merge)
```

This integration uses the HTTP API directly (no MCP client needed) since Actions runners are ephemeral and stdio transport is impractical there.

#### Transport: stdio vs HTTP

| Transport | Use case | How to run |
|---|---|---|
| **stdio** | Claude Code, local IDE plugins | `text-checker-mcp` (process started by the MCP client) |
| **HTTP (SSE)** | Jira Bot, remote agents, multi-user | `uvicorn text_checker.mcp_server:app --port 8081` |

#### Tools exposed

| Tool | Inputs | Returns |
|---|---|---|
| `correct_text` | `text: str`, `mode: str` | `corrected`, `changes[]`, `warning` |
| `list_modes` | — | `[{name, description, rag_enabled}]` |
| `ingest_document` | `content: str`, `source: str` | `chunks_indexed: int` |

`ingest_document` lets a Jira Bot or CI step push new product docs into the RAG store at runtime — no manual CLI step required.

---

## MCP + VS Code Copilot Chat — team linting with product context

This is the most impactful near-term use of the MCP server. Your team already uses GitHub Copilot (also called Codex) in VS Code. Connecting it to text-checker via MCP gives every developer access to product-aware text correction directly from the chat panel they already have open.

### Why Copilot alone isn't enough

GitHub Copilot (GPT-4o) is trained on public data. It has no knowledge of:

- Your internal product names, feature names, and acronyms
- Your company's release note format and style rules
- Your glossary of protected terms

It will happily rewrite `PROJ-1234` as something readable, guess at product terminology, or apply generic style that contradicts your guide. text-checker's RAG store has all of that ingested. When Copilot delegates to text-checker via MCP, it gets back corrections grounded in your actual product docs.

### How it works — the flow

```
Developer types in Copilot Chat panel (VS Code)
         ↓
  "Check this release note for style"
  "Fix grammar in the selected text"
  "Is this PR description consistent with our writing guide?"
         ↓
Copilot sees text-checker MCP server is available
         ↓
Copilot decides to call correct_text(text, mode) tool
         ↓
text-checker MCP server (HTTP/SSE, shared team instance)
         ↓
Full pipeline: mask → RAG retrieve → LLM → unmask → hallucination guard
         ↓
{ corrected, changes: [...], warning: false }
         ↓
Copilot presents corrected text + diff in the chat panel
```

### Team setup — one config file, zero per-developer work

Commit a single file to the repo and every team member gets the MCP connection automatically when they open the project in VS Code (requires VS Code 1.99+ and GitHub Copilot extension):

```json
// .vscode/mcp.json  ← commit this to the repo
{
  "servers": {
    "text-checker": {
      "type": "http",
      "url": "http://your-shared-server:8081/mcp"
    }
  }
}
```

The text-checker service runs on a shared host (same machine as today, or a team server). All team members' Copilot instances point to the same MCP server, which means they all share the same RAG knowledge base — update the product docs once, every developer benefits immediately.

### Architecture — shared knowledge base

![VS Code Copilot MCP integration](images/vscode-mcp-integration.png)

```
┌──────────────────────────────────────────────────────────────────┐
│                   Team (VS Code + Copilot Chat)                  │
│                                                                  │
│  Developer 1  │  Developer 2  │  Developer 3                     │
│  [Chat panel] │  [Chat panel] │  [Chat panel]                    │
│  MCP client   │  MCP client   │  MCP client                      │
└──────┬────────┴──────┬────────┴──────┬───────────────────────────┘
       │               │               │
       └───────────────┼───────────────┘
                       │  HTTP/SSE  (MCP protocol)
                       ▼
         ┌─────────────────────────────┐
         │   text-checker MCP server   │
         │   correct_text(text, mode)  │
         │   list_modes()              │
         │   ingest_document(content)  │
         └──────────────┬──────────────┘
                        │
                        ▼
         ┌─────────────────────────────┐
         │     text-checker pipeline   │
         │  mask → RAG → LLM → guard  │
         └──────────────┬──────────────┘
                        │
          ┌─────────────┴──────────────┐
          │     Shared knowledge base  │
          │  Glossary (product terms)  │  ← one store, all devs
          │  RAG store (product docs)  │  ← ingest once, shared
          └────────────────────────────┘
```

### Example conversations in Copilot Chat

**Grammar check (developer selects text, then asks)**
```
You:      Fix the grammar in this commit message:
          "Update the cache invalidation logic so its faster and doesnt
           drop keys when redis is unavailable"

Copilot:  I'll use text-checker to fix that.
          [calls correct_text(..., "grammar")]

          Corrected:
          "Update the cache invalidation logic so it's faster and doesn't
           drop keys when Redis is unavailable"

          Changes: "its" → "it's", "doesnt" → "doesn't", "redis" → "Redis"
```

**Release note (product-aware, uses RAG context)**
```
You:      Check this release note:
          "fixed issue with data sync in proj-456, now product dashboard
           updates quicker"

Copilot:  [calls correct_text(..., "release-note")]

          Corrected:
          "Fixed data sync issue in PROJ-456. Product Dashboard now
           updates faster."

          Changes: capitalised "Fixed", "PROJ-456" casing enforced,
                   "Product Dashboard" canonical casing from glossary,
                   "quicker" → "faster" (style guide preference)
```

**Style check on a PR description**
```
You:      Does this PR description match our writing style?
          [pastes PR body]

Copilot:  [calls correct_text(..., "style")]

          Here's the corrected version with 3 changes.
          Warning: edit ratio is high — the original may need a rewrite
          rather than just a style pass.
```

### Important behaviour to know

**Copilot does not lint automatically.** It is not a file-watcher. The developer must explicitly ask in the chat window. Copilot then decides to call the tool based on the request. This is different from ESLint or a save-hook — it is conversational, on demand.

If you want automatic on-save linting (like ESLint), that requires a separate VS Code extension that calls the text-checker HTTP API directly. MCP and an extension serve different purposes:

| | MCP (Copilot Chat) | VS Code Extension |
|---|---|---|
| Trigger | Developer asks in chat | File save / keystroke |
| Context | Whole conversation, selected text | Active file / selection |
| Output | Chat response with diff | Inline squiggles / Problems panel |
| Effort to build | Low (MCP server only) | Higher (separate extension) |

Start with MCP — it covers the high-value cases (release notes, PR descriptions, commit messages) with minimal build effort.

### What gets built (tasks #26 and #27)

**#26 — MCP server core** (`src/text_checker/mcp_server.py`)
Thin FastMCP wrapper over the existing HTTP API. Exposes `correct_text`, `list_modes`, `ingest_document`. Runs as a separate process on the same host, HTTP/SSE transport on port 8081.

**#27 — VS Code integration**
`.vscode/mcp.json` committed to repo, usage examples in README, end-to-end test with Copilot Chat.

---

## How they work together in text-checker

```
POST /v1/correct
       ↓
┌─────────────────────────────────────────────────────────┐
│                  text-checker pipeline                  │
│                                                         │
│  1. Mask          hide URLs, tickets, glossary terms    │
│       ↓                                                 │
│  2. RAG retrieve  fetch relevant product doc chunks     │
│       ↓                                                 │
│  3. LLM call      masked text + RAG context → Ollama   │
│       ↓                                                 │
│  4. Unmask        restore protected tokens              │
│       ↓                                                 │
│  5. Hallucination guard + edit-ratio check              │
│       ↓                                                 │
│  6. Response      corrected text + changes + warnings   │
└─────────────────────────────────────────────────────────┘
```

- **LLM** does the reasoning and text generation (step 3).
- **RAG** provides the product-specific context that makes the LLM's output accurate for your domain (step 2).
- **MCP** is the future integration layer that will let other Claude-based tools call text-checker as a first-class tool (not yet implemented).

The masking, hallucination guard, and edit-ratio thresholds are text-checker's own guardrails — the pipeline-level safety layer that protects against the LLM's inherent tendency to hallucinate or over-edit.

---

## Further reading

- [Architecture overview](architecture.md) — full system diagram and component descriptions
- [ADR-0003](decisions/0003-deterministic-pipeline-not-agent.md) — why a deterministic pipeline, not an LLM agent
- [ADR-0009](decisions/0009-chroma-embedded-for-rag-store.md) — why Chroma for the RAG vector store
- [ADR-0010](decisions/0010-llm-based-glossary-extraction.md) — LLM-based glossary extraction
- [ADR-0011](decisions/0011-tighter-rag-defaults.md) — RAG min-score calibration
- [ADR-0012](decisions/0012-glossary-rag-interaction.md) — how glossary masking and RAG interact
