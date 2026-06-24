# 0010. LLM-based glossary extraction from product docs

Date: 2026-06-17
Status: Accepted

## Context

The glossary (ADR-0004's "protected tokens" with a per-tenant term list) is most useful when populated with real product names, feature names, and internal jargon. Asking an admin to type these in by hand is tedious and inevitably incomplete. Product docs already contain the canonical names — the question is how to extract them.

Options:

1. **Manual entry only**. `glossary add <term>`, `glossary import <file>`. User responsibility to compile the list.
2. **Regex / heuristic extraction**. Title-case sequences, words near `@codeblocks`, etc. Brittle and produces a lot of noise.
3. **NER (named-entity recognition) library**. spaCy or similar. Adds a heavy dependency for a one-off ingestion task; quality is poor on internal jargon the model has never seen.
4. **LLM-based extraction**. Ask the same LLM the service already uses to identify product names, feature names, and jargon from the doc, returning structured JSON.

(1) plus (4) covers the full spectrum: manual for control, LLM for bootstrap and bulk additions. (2) and (3) are dominated.

## Decision

We will add `glossary extract <path>` that uses the configured LLM (the same one the service uses for corrections) to identify glossary candidates from a file or directory. The command supports `--add` to merge the extracted terms into the glossary in one step, otherwise it just prints them for review.

The extractor uses the existing RAG `loaders` and `chunker` to handle multi-format input (md, txt, html, pdf) and split long docs into LLM-context-sized pieces. Results are deduplicated across chunks and sorted alphabetically.

Parsing is robust: the prompt asks for a JSON array, the parser tries JSON first (finding the array inside any prose the model may emit), and falls back to line-splitting with bullet/quote/comma stripping when the model ignores the JSON instruction.

## Consequences

- Zero new dependencies — extraction reuses the provider, the loaders, the chunker, and the glossary store we already have.
- Quality of extraction depends on the model. Small models (qwen2.5:0.5b) miss subtle terms; 7B-class models do well. The user can override the model per call with `--model`.
- `--add` is opt-in. The default behavior prints suggestions for human review, because an over-eager extractor pulling generic words ("Editor", "API") into the glossary would cause the masker to over-protect and degrade correction quality.
- The extractor's system prompt explicitly excludes generic technical terms (API, HTTP, JSON, etc.) so the result is dense. This is a prompt-engineering layer that may need tuning per organization; for now it's a constant in `extractor.py`.
- Not yet implemented: incremental extraction (only new content since last run), per-tenant scoping, confidence scores, or human-review workflow. All deferred to Phase 2 of the glossary + RAG work.
