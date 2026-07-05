FROM python:3.12-slim AS builder

# Proxy support for builds behind a corporate proxy. Pass at build time:
#   docker build --build-arg HTTP_PROXY=... --build-arg HTTPS_PROXY=... \
#                --build-arg NO_PROXY=... -t text-checker:dev .
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml ./
COPY uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev 2>/dev/null || \
    uv sync --no-install-project --no-dev
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN useradd -u 1000 -m -s /bin/bash app
COPY --from=builder --chown=app:app /app /app
USER app
# SERVICE_HOST / SERVICE_PORT are the bind for uvicorn. Both are honored
# by the CMD, HEALTHCHECK, and the Makefile / systemd unit so a single
# env change moves the port everywhere.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_HOST=0.0.0.0 \
    SERVICE_PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('SERVICE_PORT','8080'); sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/healthz').status==200 else 1)"
# Shell form with explicit exec so SIGTERM is forwarded to uvicorn (not
# absorbed by /bin/sh). Env vars expand at container start, so `docker run
# -e SERVICE_PORT=9090 ...` binds uvicorn to that port with no image rebuild.
CMD exec uvicorn text_checker.main:app --host ${SERVICE_HOST} --port ${SERVICE_PORT}
