# 0006. Per-mode edit-ratio thresholds, tuned after live testing

Date: 2026-06-17
Status: Accepted

## Context

The hallucination guard uses an edit-ratio threshold — character-level `1 - SequenceMatcher.ratio()` — as one of its checks. Each mode needs its own threshold because the expected scale of edits varies enormously:

- Grammar: typically a few character-level fixes per sentence
- Style: tighter phrasing, may rewrite phrases
- Jira story: a wholesale restructure into "As a … I want …"
- Release note: rewrites into verb-first one-liners

Initial values (chosen by intuition):

| Mode | First threshold |
|---|---|
| `grammar` | 0.30 |
| `style` | 0.55 |
| `jira-story` | 0.80 |
| `release-note` | 0.80 |

Live testing surfaced a problem: `their going home tonigt` → `They're going home tonight.` has a character-level edit ratio of ~0.35, which exceeded the grammar threshold of 0.30. The guard rejected a correct correction. The flaw: edit ratio doesn't scale with input length. A short input with two errors has a higher ratio than a long input with one error, but both are legitimate fixes.

## Decision

We will raise the grammar threshold from 0.30 to 0.45 and the style threshold from 0.55 to 0.60. Jira-story and release-note stay at 0.80.

A regression test pins the failing example so the threshold cannot drift back below it: `test_guard_allows_short_input_with_multiple_grammar_fixes` in `tests/unit/test_postprocess.py`.

## Consequences

- Short inputs with two or three legitimate grammar fixes now pass the guard.
- The guard still rejects wholesale rewrites at grammar level (e.g., `hi` → `Here is a much longer rewrite of your text.`).
- The threshold remains an over-simplification — it punishes short, dense inputs more than long sparse ones. A future refinement (Phase 2) would either scale the threshold with input length, or use a length-normalized edit distance, or add a content-preservation check that counts surviving content words. None of those are in scope for Stage 1.
- Thresholds are constants in `postprocess.py`, not config. Treating them as code (and putting regression tests on the cases they should accept) is more honest than letting operators tune them in `.env` and risk silently breaking quality.
