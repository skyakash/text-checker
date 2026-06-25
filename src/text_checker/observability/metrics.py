from prometheus_client import CollectorRegistry, Counter, Histogram, make_asgi_app

registry = CollectorRegistry()

requests_total = Counter(
    "correct_requests_total",
    "Number of /v1/correct calls by mode, model, and outcome.",
    ["mode", "model", "status"],
    registry=registry,
)

latency_seconds = Histogram(
    "correct_latency_seconds",
    "End-to-end correction latency in seconds.",
    ["mode", "model"],
    registry=registry,
)

rag_retrieval_score = Histogram(
    "rag_retrieval_score",
    "Cosine similarity scores of chunks returned by RAG retrieval, before min_score filtering. Use this to calibrate RAG_MIN_SCORE for your corpus.",
    ["mode"],
    buckets=(0.0, 0.2, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9, 1.0),
    registry=registry,
)

metrics_app = make_asgi_app(registry=registry)
