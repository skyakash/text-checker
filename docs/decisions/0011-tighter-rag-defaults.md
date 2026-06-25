# 0011. Tighter RAG defaults: min_score floor and skip for grammar mode

Date: 2026-06-25
Status: Accepted

## Context

Live testing after Stage 2 shipped surfaced a real failure mode: a grammar-mode call on `flowstate is going to be reased next quartar` came back flagged, with `corrected_text` equal to the user's original input. The trace:

1. Pre-processor masked `flowstate` → `<<MASK_5>>` (glossary protection).
2. RAG retrieved three chunks with scores 0.55–0.57 — all about Phase 1 roadmap and decisions, none related to the input.
3. System prompt was augmented with that irrelevant context.
4. Model saw `<<MASK_5>> is going to be reased next quartar` plus a wall of Phase-1 roadmap text and decided the placeholder should be filled in. It returned `Phase 1 is going to be released next quarter.` — replacing the placeholder with text inferred from RAG context.
5. Hallucination guard correctly caught the dropped placeholder and returned the original text with `flagged: true`.

The guard did the right thing. The system safely refused the bad correction. But two underlying defaults were wrong:

- **`RAG_MIN_SCORE=0.0`** let weak matches (score ~0.55) into the prompt. Stage 2 shipped this default for "see anything you can find" debugging convenience; in production it's actively harmful.
- **RAG fired for `mode=grammar`.** Grammar is a character-level fix. Product context cannot help spell `released` correctly, and as this case showed, it can actively mislead the model into substituting placeholder content from the context block.

## Decision

Two default changes:

1. **`RAG_MIN_SCORE` default raised from `0.0` to `0.65`.** Chunks with cosine similarity below 0.65 are dropped before reaching the prompt. The value is conservative enough to drop the 0.55-class matches that caused the original failure, while still passing the 0.7+ matches we see for genuinely relevant retrievals.
2. **New `RAG_SKIP_MODES` setting, default `"grammar"`.** When the request mode is in this comma-separated set, RAG is skipped entirely for the request — the embedder is not called, no context is retrieved. A per-request `use_rag: true` override forces RAG on regardless (preserves the existing explicit-override semantics).

Both values are configurable via env vars; the defaults reflect the lesson from live testing.

A regression test in `tests/unit/test_rag_orchestrator.py` pins the exact failing input pattern: a grammar-mode call with a seeded RAG store must return `rag_context_used: []` and must not call the embedder. A separate test pins the production defaults (0.65 and `"grammar"`) so a careless config edit cannot silently widen either.

## Consequences

- The original failing case (`flowstate is going to be reased next quartar`, mode=grammar) now produces a correct grammar fix because the RAG context never reaches the prompt.
- The 0.65 floor will hide chunks that are *somewhat* relevant. This is the right trade — for product-context RAG, "slightly relevant" is worse than "nothing" because the model treats injected context as authoritative. Operators who want broader retrieval can lower `RAG_MIN_SCORE` per deployment.
- Operators who *do* want RAG to enrich a grammar correction (e.g., to preserve specific spelling in a technical doc) set `RAG_SKIP_MODES=""` or pass `use_rag: true` per request. The path is documented in the README.
- The skip is mode-specific by design, not "is the input short" or "did we find weak matches" — those are heuristics that need their own tuning. Mode is a clear, caller-controlled signal.
- Phase 2 may extend this to per-mode `RAG_TOP_K` and per-mode `RAG_MIN_SCORE` (e.g., release-note tolerates more context than jira-story). For now one floor and one skip-set keeps the configuration small.
