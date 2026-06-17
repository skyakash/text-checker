from prometheus_client import CollectorRegistry, Counter, Histogram, make_asgi_app

registry = CollectorRegistry()

requests_total = Counter(
    "correct_requests_total",
    "Number of /v1/correct calls.",
    ["mode", "model", "status"],
    registry=registry,
)

latency_seconds = Histogram(
    "correct_latency_seconds",
    "End-to-end correction latency in seconds.",
    ["mode", "model"],
    registry=registry,
)

metrics_app = make_asgi_app(registry=registry)
