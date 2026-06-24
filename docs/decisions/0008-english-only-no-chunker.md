# 0008. English-only inputs with a 5000-char hard limit

Date: 2026-06-17
Status: Accepted

## Context

Two related scope decisions:

**Language.** The internal tools we're serving (Jira, release notes, Confluence) operate primarily in English. Adding multilingual support would force a multilingual base model (Qwen 2.5, Aya), broader eval data per language, and per-language quality monitoring. The marginal value at Stage 1 is unclear.

**Input length.** Long inputs (multi-paragraph documents, long Confluence pages) don't fit a single model context cleanly. Handling them well requires a sentence-aware chunker that splits the input, corrects each chunk, and stitches the results with overlap-dedupe at chunk boundaries. The chunker itself is non-trivial code that needs its own test surface.

## Decision

Stage 1 will:
- Reject inputs the language heuristic identifies as non-English with HTTP 422
- Reject inputs over 5000 characters with HTTP 413

The language check is a heuristic on ASCII-letter ratio (`≥ 0.9`), not a `langdetect` model. The length limit is a hard constant in `preprocess.py`, not configurable.

## Consequences

- We can pick English-strong models (Qwen, Hermes 3) without compromising on multilingual coverage.
- Edge cases (mixed-language Jira tickets, English with many accented words) may false-trigger the heuristic. We accept the false-positive rate at Stage 1; replacing with `langdetect` is a Phase 1 candidate if real usage surfaces problems.
- 5000 characters covers the overwhelming majority of internal Jira descriptions and release-note lines we see. Multi-paragraph Confluence pages won't work — they fail loudly with 413, with a clear error.
- The chunker is explicitly deferred to Phase 3. Adding it requires real test data (long inputs from real consumers) which we don't have yet.
- A consumer that needs longer inputs today can pre-split client-side and concatenate results. This is documented in troubleshooting.
