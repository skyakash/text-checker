# text-corrector

Internal text correction service. Exposes an HTTP API that internal tools (Jira bot, release-notes generator, CLI helpers) call to grammar-, style-, and clarity-correct text. Designed to swap LLM backends (Ollama locally, vLLM/TGI on GPU, Anthropic/OpenAI in the cloud) without changing service code.

See [docs/architecture.md](docs/architecture.md) for the design and roadmap.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
cp .env.example .env
make install
make dev
```

Then:

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/v1/modes
```

## Local stack with Ollama

```bash
make up   # builds the service image and starts ollama + prometheus
```

Pull a small model into Ollama once it is up:

```bash
docker compose exec ollama ollama pull qwen2.5:0.5b
```

## Layout

```
src/text_corrector/
  api/             HTTP layer (routes, schemas, auth, rate limit)
  pipeline/        Pre-process, prompt build, post-process
  providers/       Provider abstraction + concrete clients
  observability/   Prometheus metrics, OpenTelemetry traces
tests/
  unit/            Pure-Python unit tests
  contract/        Provider contract tests (mocked)
  integration/     End-to-end against a real Ollama
  eval/            Golden-dataset quality harness
deploy/
  k8s/             Helm chart and manifests (later)
  prometheus.yml   Local Prometheus scrape config
```
