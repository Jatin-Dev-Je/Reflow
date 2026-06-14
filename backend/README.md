# Reflow Backend

Trustworthy Autonomous Payment Recovery Platform — backend service.

> Every failed payment should be investigated, explained, and recovered automatically — with verifiable evidence, policy-enforced execution, and zero double-charge risk.

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| Web | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL + pgvector |
| Cache / Queue | Redis + ARQ |
| Realtime | python-socketio |
| LLM | LiteLLM (Groq / Gemini / OpenRouter — free tiers) |
| Agents | Pydantic AI + custom orchestrator |
| Embeddings | fastembed (bge-small-en-v1.5) |
| Policy | Custom rule engine (Pydantic) |
| Auth | FastAPI Users |
| Observability | OpenTelemetry + Langfuse + structlog |
| Testing | pytest + Hypothesis + Locust |

## Architecture

Clean / Hexagonal architecture with DDD bounded contexts:

```
src/reflow/
├── core/           # Cross-cutting infrastructure (config, db, redis, events, ...)
├── domain/         # Pure domain — entities, value objects, events, repo interfaces
├── application/    # Use cases (CQRS — commands & queries)
├── agents/         # AI layer — diagnosis, strategy, risk, guard + orchestrator
├── infrastructure/ # Adapters — persistence, gateways, policy engine, audit log
├── api/            # FastAPI routes + webhooks + WebSocket
└── workers/        # ARQ background workers
```

Bounded contexts: `transactions`, `diagnosis`, `strategy`, `risk`, `policy`, `recovery`, `health`, `audit`, `memory`.

## Running locally

### Prerequisites
- Docker Desktop (for Postgres + Redis)
- Python 3.12+
- [uv](https://github.com/astral-sh/uv): `pip install uv` (or `pipx install uv`)

### First-time setup

```bash
cd backend

# 1. Install dependencies + create venv
uv sync

# 2. Configure environment — copy and edit if needed
cp .env.example .env

# 3. Start Postgres (with pgvector) + Redis
docker compose up -d

# Schema is auto-loaded from migrations/sql/001_initial_schema.sql on first start.
```

### Run the API

```bash
make run          # uvicorn with --reload, on http://localhost:8000
```

Open:
- `http://localhost:8000/healthz` — liveness
- `http://localhost:8000/readyz` — readiness (checks Redis)
- `http://localhost:8000/docs` — OpenAPI / Swagger UI
- `http://localhost:8000/api/v1/transactions` — list transactions

### Smoke test the full flow

Send a synthetic failed payment to the mock-gateway webhook:

```bash
curl -X POST http://localhost:8000/api/webhooks/mock-gateway \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "tx_smoke_001",
    "amount_cents": 4999,
    "currency": "USD",
    "card": {"bin": "424242", "last4": "4242", "brand": "visa", "funding": "credit", "country": "US"},
    "gateway_provider": "mock",
    "outcome": "soft_decline",
    "decline": {
      "code_raw": "insufficient_funds",
      "code_normalized": "FUNDS_INSUFFICIENT",
      "category": "funds",
      "message": "Insufficient funds"
    }
  }'
```

Then fetch the Trust View timeline (use the `transaction_id` returned above):

```bash
curl http://localhost:8000/api/v1/transactions/<id>/timeline
```

### Tests

```bash
make test-unit          # 51 unit + property-based tests (no I/O)
make test-int           # integration tests via testcontainers (needs Docker)
make test               # full suite
make test-cov           # with coverage report
```

### Code quality

```bash
make fmt        # ruff format
make lint       # ruff check --fix
make typecheck  # mypy strict
```

## Status

Foundation + event store + first vertical slice complete.
See `docs/api/endpoint-plan.md` for the full API roadmap (~108 endpoints).
