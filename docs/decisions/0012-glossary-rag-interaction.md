# 0012. Mask glossary terms inside RAG chunks, and canonicalize the guard's mask check

Date: 2026-06-25
Status: Accepted

## Context

ADR-0004 masks glossary terms in the *input* so the LLM never sees them. ADR-0009/0011 introduced RAG retrieval that injects product-doc chunks into the system prompt. Live testing on 2026-06-25 showed these two pieces interact badly when both are on:

The input "we improved the hallucination guard in text-checker" with `"Hallucination Guard"` in the glossary and `release-note` mode pulled three chunks from ADR-0005/0004/0006 — all literally about the hallucination guard — and injected them into the system prompt. Both `qwen2.5:7b-instruct` and `hermes3:8b` then produced wrong output:

- **qwen** wrote `"We improved the hallucination guard in text-checker."` — inferred the masked term's value from context and substituted it, but in lowercase. The guard's substring check is case-sensitive, so it rejected `"Hallucination Guard"` missing from the output and returned the user's original text with `flagged: true`.
- **hermes** wrote `"Improved the original text in both masked placeholders, preserving their exact content and order."` — meta-described its instruction instead of executing it. Same flag.

Same input with `use_rag: false` worked perfectly on both models. The failure is **structural**: the masker hides the term from the input while RAG actively shows it in context. The model can't ignore that conflict, and a bigger model would do this less often but not never.

## Decision

Two fixes, complementary:

1. **Mask glossary terms inside RAG chunks before they reach the prompt.** When the retriever returns chunks, the orchestrator rewrites each chunk's text — every occurrence of a glossary term (case-insensitive, word-boundary) becomes the *same* placeholder the input masker assigned. The model sees `<<MASK_5>>` in both the input and the surrounding context, so there is nothing to substitute. Implemented as `preprocess.reapply_glossary_masks()` and a new `MaskedInput.glossary_placeholders` field that tracks which placeholders came from the glossary (so URL/mention/ticket masks keep their strict substring semantics).
2. **Case-insensitive canonicalization before the guard runs.** A new `postprocess.canonicalize_glossary_terms()` finds any case-different occurrence of a glossary value in the model output and normalizes it to the glossary's canonical case. Runs after `unmask()`, before `hallucination_guard()`. If the model writes "flowstate" when the glossary says "Flowstate", the output becomes "Flowstate" and the guard's substring check passes.

Fix #1 prevents the failure from occurring most of the time. Fix #2 is the safety net for the cases that get through anyway.

## Consequences

- The previously-failing input `we improved the hallucination guard in text-checker` now produces `we improved the Hallucination Guard in the text-checker service`, `flagged: false`, with RAG context still populated. Confirmed against live qwen2.5:7b-instruct on 2026-06-25.
- RAG chunks may now contain placeholder tokens (`<<MASK_5>>`) when displayed in the system prompt. This is correct behavior, but operators inspecting prompts via debug logging will see placeholders inline.
- `MaskedInput` gained a `glossary_placeholders: set[str]` field. Callers that constructed `MaskedInput` directly (none in the project today, but anything downstream) need to know about it. `reapply_glossary_masks` and `canonicalize_glossary_terms` ignore non-glossary placeholders, so URL/mention/ticket handling is unchanged.
- The canonicalize step is idempotent: text already in canonical case passes through unmodified. Safe to call always.
- The fix is **per-request** and **stateless** — no new config knob, no behavior change visible to clients beyond the resolved bug.

## Tested cases

- `test_glossary_terms_are_masked_inside_rag_chunks` — chunks containing the term reach the model as placeholders, not the term itself.
- `test_lowercase_glossary_in_model_output_is_canonicalized_and_accepted` — model writes term in lowercase; output uses canonical case and guard passes.
- `test_canonicalize_does_not_alter_non_glossary_masks` — URL masks unchanged by canonicalize.
- `test_canonicalize_corrects_lowercase_match` and four sibling unit tests in `test_postprocess_canonicalize.py`.
- `test_reapply_replaces_glossary_term_with_placeholder` and five sibling tests in `test_preprocess_reapply.py`.
- `test_mask_tracks_glossary_placeholders_separately_from_pattern_masks` — `MaskedInput.glossary_placeholders` is populated correctly and only by glossary masks.

153/153 tests pass.
