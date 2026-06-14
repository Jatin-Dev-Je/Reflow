# 0001 — Modular Monolith with Extraction Seams

**Status:** Accepted
**Date:** 2026-06-14

## Context

Reflow needs a backend that can:
- Ship in weeks, not quarters
- Be operated by a small team
- Scale to multi-tenant production later
- Stay testable and explorable end-to-end on a laptop
- Decompose into services *only* when a real bottleneck demands it

Microservices upfront would burn the entire delivery budget on cross-service plumbing. A pure monolith risks ossification once teams scale. We need a third path.

## Decision

A **modular monolith** with explicit **extraction seams**:

- Single Python codebase under `src/reflow/`
- Multiple deployable processes from the same code: `api`, `ws`, `webhook`, `recovery-worker`, `diagnosis-worker`, `learning-worker`, `outbox-relay`, `simulator`
- Bounded contexts (`transactions`, `diagnosis`, `strategy`, `risk`, `policy`, `recovery`, `health`, `intel`, `audit`, `obs`) are physically separated as folders with no cross-imports of internals — only their public application interfaces
- Inter-context communication happens via **domain events through the event store + Redis Streams**, not direct method calls — even though they run in-process
- Database schemas are namespaced per context (Postgres `core`, `txn`, `agent`, `policy`, `recovery`, `health`, `intel`, `audit`, `obs`, `sim`, `flags`)

This means any context can later become its own service by:
1. Splitting its DB schema into a separate database
2. Moving its event handlers behind a network boundary
3. No code refactor required

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **Pure monolith, no boundaries** | Bounded contexts blur, refactoring becomes scary at month 6 |
| **Microservices from day one** | 4-10x engineering overhead for our scale; we'd ship nothing |
| **Functional / serverless** | Cold starts and per-invocation costs break LLM-heavy workloads; observability fragments |
| **Event-sourced microservices** | All the cost of microservices *plus* ES complexity, with no proportional benefit yet |

## Consequences

**Easier:**
- One deployment, one set of secrets, one observability target — until we hit scale
- Local dev parity with prod via single `docker compose up`
- Cross-context refactors stay in one PR
- Tests can run the entire saga in-process

**Harder:**
- Discipline required: nothing prevents a developer from importing across context internals at 2 AM
- Single Postgres / single Redis can become a contention point at scale
- One CI pipeline; one bad migration affects everything

**Mitigations:**
- `ruff` import-boundary rules block cross-context internal imports
- Architecture tests in `tests/unit/` assert that domain layers do not import from infrastructure
- Schema namespacing means we can split databases without renaming tables
- The outbox + event bus mean cross-context communication is *already* asynchronous, so extraction is a deployment change, not a code change
