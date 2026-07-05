# VS Code Copilot Chat integration

> Read this if you want your team to invoke text-checker from the VS Code chat panel.

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
{ corrected_text, diff: [...], flagged: false }
         ↓
Copilot presents corrected text + diff in the chat panel
```

### Team setup — one config file, zero per-developer work

Commit a single file to the repo and every team member gets the MCP connection automatically when they open the project in VS Code (requires VS Code 1.99+ and GitHub Copilot extension):

```json
// .vscode/mcp.json  ← commit this to the repo (the real file is already in this repo)
{
  "servers": {
    "text-checker": {
      "type": "http",
      "url": "http://your-shared-server:8081/mcp",
      "headers": { "X-API-Key": "${input:textCheckerMcpKey}" }
    }
  },
  "inputs": [
    {
      "id": "textCheckerMcpKey",
      "type": "promptString",
      "description": "text-checker MCP API key",
      "password": true
    }
  ]
}
```

The `X-API-Key` header is required — the MCP HTTP transport rejects unauthenticated requests (and fails closed if the server itself has no key configured). The `${input:...}` prompt means each developer supplies the key locally; it is never committed.

The text-checker service runs on a shared host (same machine as today, or a team server). All team members' Copilot instances point to the same MCP server, which means they all share the same RAG knowledge base — update the product docs once, every developer benefits immediately.

### Architecture — shared knowledge base

![VS Code Copilot MCP integration](../images/vscode-mcp-integration.png)

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
         │   list_models()             │
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

### What shipped (tasks #26 and #27 — done)

**#26 — MCP server core** (`src/text_checker/mcp_server.py`)
Thin FastMCP wrapper over the existing HTTP API. Exposes `correct_text`, `list_modes`, `list_models`, `ingest_document`. Runs as a separate process, stdio by default or streamable HTTP on port 8081 (`--http`), with fail-closed `X-API-Key` auth. See ADR-0015.

**#27 — VS Code integration**
`.vscode/mcp.json` committed to this repo; usage examples in the README ("Use from VS Code Copilot Chat").

