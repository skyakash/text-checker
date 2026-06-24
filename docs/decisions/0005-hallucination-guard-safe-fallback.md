# 0005. Hallucination guard returns the original text, not an error

Date: 2026-06-17
Status: Accepted

## Context

The hallucination guard fails a correction when any of:

- the model dropped or altered a masked placeholder
- a masked input token is missing from the output
- the edit ratio exceeds a per-mode threshold
- the model introduced more than two new capitalized "entity-like" tokens

What should the service do when the guard rejects?

Option A: return HTTP 200 with `flagged: true`, the user's **original text** as `corrected_text`, and the model's actual output in a `model_output` debug field.

Option B: return HTTP 4xx with the rejection reason. Caller must handle the failure.

## Decision

We will adopt Option A. When the guard rejects, the service returns 200 OK with the user's original text in `corrected_text`, the rejection reason in `flag_reason`, and the rejected model output in `model_output` for inspection.

## Consequences

- Internal callers (Jira bot, release-notes tool) get a safe default — text they can ship — without writing error-handling code for every call site. The semantic is "I tried to improve this; here's the best safe answer."
- A consumer that *does* want strict semantics can check `flagged` and act on it.
- The model's output is preserved (in `model_output`) so callers can debug, audit, or even decide to ship the rejected output anyway under their own policy.
- Operators can monitor the `flagged` rate as a metric (`correct_requests_total{status="flagged"}`). A rising flagged rate is an early indicator that a model is degrading or that prompts need retuning, without paging anyone.
- The guard becomes a quality dial we can tighten without breaking callers — moving a threshold won't suddenly cause 4xx errors in production.
