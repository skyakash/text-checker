# 0002. Ollama as the default local provider, not LMStudio

Date: 2026-06-17
Status: Accepted

## Context

The original requirement called out LMStudio as a candidate for hosting local models. We considered LMStudio, Ollama, llama.cpp's `llama-server`, vLLM, and Hugging Face TGI.

LMStudio is a GUI-first desktop application. Its server mode exists but is not the primary use case, and it expects a human to launch it and manage models through the UI. Ollama, by contrast, is built for headless use: a single daemon, a CLI for model management (`ollama pull`, `ollama list`), an OpenAI-compatible HTTP server on a fixed port, and Docker images that work the same as the host install.

vLLM and TGI are higher-throughput but require GPU. We're CPU-only on the dev path.

llama.cpp's `llama-server` is closer to Ollama in shape but requires manual GGUF management.

## Decision

We will use Ollama as the default local provider for Stage 1. The service expects an Ollama-compatible OpenAI endpoint on `OLLAMA_BASE_URL`, defaulting to `http://localhost:11434/v1`. vLLM and `llama-server` work transparently through the same provider class because they speak the same HTTP shape.

## Consequences

- Local dev experience: install Ollama, `ollama pull qwen2.5:7b-instruct`, the service works. No GUI required, no manual GGUF management.
- The `docker-compose.yml` includes an Ollama service alongside the app, so the full stack comes up with `make up`.
- LMStudio users are not blocked — LMStudio's server mode is OpenAI-compatible, so pointing `OLLAMA_BASE_URL` at LMStudio's URL works without code changes. But it's not the default, and it's not the path the README documents.
- When GPU is available, swapping to vLLM is a `OLLAMA_BASE_URL` change. The variable name keeps "ollama" for historical reasons; renaming it is a one-line change if it becomes confusing.
