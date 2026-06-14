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

## Status

Scaffolding in place. Implementation begins next.
