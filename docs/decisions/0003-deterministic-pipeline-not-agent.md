# 0003. A deterministic pipeline, not an agent

Date: 2026-06-17
Status: Accepted

## Context

The "agent" architecture — an LLM that plans, decides which tools to call, observes results, and iterates — is the dominant pattern in modern LLM products. For text correction, we considered building this way:

- Tool: lookup glossary (per-tenant protected terms)
- Tool: lookup style rules
- Tool: retrieve similar approved corrections (RAG)
- Tool: rewrite text
- Tool: self-critique

The agent would plan which tools to call per request.

The alternative is a fixed pipeline: pre-process → prompt build → LLM call → post-process. No decisions at runtime, no tool-routing nondeterminism, no multi-turn LLM loops.

## Decision

We will build Stage 1 as a deterministic pipeline. The orchestrator runs the same four stages on every request. The LLM is called exactly once per request.

We will revisit the agent question only for `quality_tier=high` in Phase 3, where a tightly-bounded **critic → reviser** loop (max one revision) provides real value for customer-facing content. Everything else stays in the pipeline.

## Consequences

- Latency and cost are predictable — one LLM call per request, no fan-out.
- Failure modes are debuggable. When something goes wrong, the failure is in a specific stage, not "the agent decided wrong."
- We give up the agent's ability to dynamically route around problems. For our task this isn't a real loss: we already know what information the model needs (mode prompt, masked input), so we hand it to the model up front instead of letting an LLM "decide" to look it up.
- Phase 3 adds the critic-reviser loop as an opt-in `quality_tier=high` feature. It's bounded (one revision max) and structured (critic emits JSON). It is the *only* agent-shaped thing in the design, and it's earned its keep by a specific quality requirement (release notes, customer emails).
