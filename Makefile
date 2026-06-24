.PHONY: install dev test lint fmt typecheck up down build clean

install:
	uv sync --all-extras --group dev

dev:
	uv run uvicorn text_checker.main:app --reload --host 0.0.0.0 --port 8080

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
