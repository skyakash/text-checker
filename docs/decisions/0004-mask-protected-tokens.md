# 0004. Mask protected tokens before the LLM sees them

Date: 2026-06-17
Status: Accepted

## Context

User input frequently contains content that the model must not rewrite under any circumstance:

- Ticket IDs (`PROJ-123`) used as anchors in Jira automation
- `@mentions` that resolve to real users in Slack / Jira
- URLs that must remain clickable and accurate
- Code blocks where any character change would break compilation
- Inline code references with the same constraint

Even strong models occasionally rewrite these — turning `@alice` into "Alice", trimming a query string off a URL, splitting `PROJ-123` into "Project 123". The cost of such a "correction" is real: broken automation, dead links, lost references.

Two paths to handle this:

1. **Prompt-only**: instruct the model strongly not to touch these tokens. Relies on instruction-following quality.
2. **Mask deterministically**: replace each protected token with an opaque placeholder (`<<MASK_n>>`) before sending to the model, restore after generation, and verify the placeholders survived.

## Decision

We will mask protected tokens deterministically in the pre-process stage and restore them in the post-process stage. Five patterns are masked, in order: code fences, inline code, URLs, `@mentions`, ticket IDs (`[A-Z]{2,}-\d+`). The hallucination guard verifies every masked token's original value appears in the unmasked output, failing the request safely if any are missing.

## Consequences

- Protected tokens cannot be rewritten by the model under any prompt, any temperature, any model size. The guarantee is a regex, not a hope.
- The model sees `see <<MASK_3>> about <<MASK_4>>` instead of `see @alice about PROJ-123`. Small models occasionally try to "explain" the placeholders; the guard's leftover-MASK check catches this.
- New patterns (custom internal identifiers, specific email formats) are added to the masker by editing `_PATTERNS` in `preprocess.py`. No model change required.
- The masker is the security boundary for protected content. Tests exercise round-trip behavior for each pattern individually and in combination.
