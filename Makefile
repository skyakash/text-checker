.PHONY: install dev test lint fmt typecheck up down build clean

# Bind can be overridden per environment — set SERVICE_HOST and SERVICE_PORT
# in the shell or a .env file before `make dev`. Matches the MCP server's
# MCP_HOST / MCP_PORT convention (mcp_server.py).
SERVICE_HOST ?= 0.0.0.0
SERVICE_PORT ?= 8080

install:
	uv sync --all-extras --group dev

dev:
	uv run uvicorn text_checker.main:app --reload --host $(SERVICE_HOST) --port $(SERVICE_PORT)

test:
	uv run pytest

test-integration:
	uv run pytest -m integration -v

eval:
	uv run python -m text_checker.eval $(ARGS)

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

typecheck:
	uv run mypy src

up:
	docker compose up --build

down:
	docker compose down

build:
	docker build -t text-checker:dev .

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
