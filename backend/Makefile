# Reflow backend — common dev tasks.
# Usage: `make help`

.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test test-unit test-int test-cov \
        up down logs psql redis-cli migrate revision seed run worker clean

PY ?= python
UV ?= uv

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	      /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---- Setup ----
install:  ## Install all deps (incl. dev) with uv
	$(UV) sync

# ---- Quality ----
fmt:  ## Format with ruff
	$(UV) run ruff format src tests

lint:  ## Lint with ruff
	$(UV) run ruff check src tests --fix

typecheck:  ## Static type checking with mypy
	$(UV) run mypy src

# ---- Tests ----
test:  ## Run full test suite
	$(UV) run pytest

test-unit:  ## Unit tests only (no I/O)
	$(UV) run pytest -m unit

test-int:  ## Integration tests (requires Postgres + Redis)
	$(UV) run pytest -m integration

test-cov:  ## Tests with coverage
	$(UV) run pytest --cov --cov-report=term-missing --cov-report=html

# ---- Local infra ----
up:  ## Start Postgres + Redis
	docker compose up -d

down:  ## Stop local infra
	docker compose down

logs:  ## Tail local infra logs
	docker compose logs -f

psql:  ## Psql shell into local Postgres
	docker compose exec postgres psql -U reflow -d reflow

redis-cli:  ## Redis CLI into local Redis
	docker compose exec redis redis-cli

# ---- DB migrations ----
migrate:  ## Apply latest migrations
	$(UV) run alembic upgrade head

revision:  ## Create new auto-generated migration (use msg="...")
	$(UV) run alembic revision --autogenerate -m "$(msg)"

seed:  ## Seed dev data
	$(UV) run python scripts/seed_db.py

# ---- Run services ----
run:  ## Run FastAPI in dev (reload on change)
	$(UV) run uvicorn reflow.asgi:app --host 0.0.0.0 --port 8000 --reload

worker:  ## Run background workers
	$(UV) run python -m reflow.workers.main

# ---- Cleanup ----
clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
