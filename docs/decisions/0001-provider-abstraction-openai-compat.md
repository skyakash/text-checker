# 0001. Provider abstraction at the OpenAI-compatible HTTP layer

Date: 2026-06-17
Status: Accepted

## Context

The service must let us swap LLM backends without rewriting code. Candidate backends include Ollama (local dev), llama.cpp's `llama-server` and vLLM (heavier local), and Anthropic / OpenAI / Together (cloud).

There are two reasonable layers to abstract at:

1. **The vendor SDK layer**: write an `AnthropicProvider` that uses the Anthropic Python SDK, an `OpenAIProvider` that uses the OpenAI SDK, an `OllamaProvider` that uses the Ollama Python library. Each provider class wraps a different client.
2. **The HTTP layer**: write a single `OpenAICompatProvider` that speaks the OpenAI chat-completions HTTP API. Every candidate backend already supports this interface (Ollama, vLLM, llama.cpp, Anthropic, OpenAI).

Path (1) is more flexible — native SDKs expose features that the OpenAI-compat shim doesn't (extended thinking, tool-use schemas, streaming nuances). Path (2) is simpler — one client, one set of contract tests, one place where retries and timeouts live.

## Decision

We will abstract at the OpenAI-compatible HTTP layer. The service ships with one concrete provider class (`OpenAICompatProvider`), and different backends are configured by passing different `base_url` and `api_key` values.

## Consequences

- Adding a new backend that speaks OpenAI-compat (the de-facto standard) is a configuration change, not a code change.
- One `respx`-based contract test suite covers all backends — every provider is the same client class.
- We give up access to vendor-specific features. If we later need Anthropic extended thinking or OpenAI structured outputs in a way that the OpenAI-compat shim doesn't expose, we add a second provider class then. We do not preemptively add it.
- Streaming responses are not in Stage 1, so the streaming-shape differences between vendors aren't yet a concern.
