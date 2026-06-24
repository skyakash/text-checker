# Architecture Decision Records

Short, dated records of the meaningful choices made on this project — the kind of decision where, six months from now, someone reading the code would otherwise wonder "why did they do it that way?".

## Why ADRs

The codebase shows *what* the system does. Comments explain *what* a function does. ADRs explain *why* the system has the shape it has — what the alternatives were, what was rejected, and what trade-off was accepted. They survive contributor turnover and personnel change in a way that conversation history does not.

A decision that's worth an ADR has at least one of:
- A real alternative we considered and rejected
- A constraint or context that won't be obvious from the code
- A reversible-but-costly choice (would take a real rewrite to change)

A decision is *not* worth an ADR if it's just standard practice, has no real alternative, or could be changed in an afternoon.

## Format

Each ADR is a short Markdown file named `NNNN-short-slug.md`. Sections:

```markdown
# NNNN. Title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by NNNN

## Context
What forces the decision? What problem are we solving? What constraints apply?

## Decision
What did we decide? In active voice — "we will use X" — not "X was used."

## Consequences
What follows from this — both the wins and the costs we accept. Note what becomes harder.
```

Status flow: `Proposed → Accepted → Superseded by NNNN`. We don't delete superseded ADRs; we mark them and add the new one.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-provider-abstraction-openai-compat.md) | Provider abstraction at the OpenAI-compatible HTTP layer | Accepted |
| [0002](0002-ollama-default-not-lmstudio.md) | Ollama as the default local provider, not LMStudio | Accepted |
| [0003](0003-deterministic-pipeline-not-agent.md) | A deterministic pipeline, not an agent | Accepted |
| [0004](0004-mask-protected-tokens.md) | Mask protected tokens before the LLM sees them | Accepted |
| [0005](0005-hallucination-guard-safe-fallback.md) | Hallucination guard returns the original text, not an error | Accepted |
| [0006](0006-edit-ratio-thresholds.md) | Per-mode edit-ratio thresholds, tuned after live testing | Accepted |
| [0007](0007-in-memory-state-stage1.md) | In-memory rate-limit and idempotency for Stage 1 | Accepted |
| [0008](0008-english-only-no-chunker.md) | English-only inputs with a 5000-char hard limit | Accepted |
