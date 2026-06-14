# Architecture Decision Records

ADRs document load-bearing architectural decisions: what we chose, what we rejected, and why. Future engineers (including future-us) need this context to safely change the system.

## Format

Each ADR is named `NNNN-slug.md` and follows:

```
# Title
Status: Proposed | Accepted | Superseded by NNNN
Date: YYYY-MM-DD

## Context
What problem are we solving? What constraints apply?

## Decision
What did we choose?

## Alternatives Considered
What else did we look at? Why did we reject them?

## Consequences
What does this make easier? What does it make harder?
```

## Index

| ID | Title | Status |
|---|---|---|
| [0001](./0001-modular-monolith.md) | Modular Monolith with Extraction Seams | Accepted |
| [0002](./0002-event-sourcing-outbox.md) | Event Sourcing with Transactional Outbox | Accepted |
| [0003](./0003-custom-policy-engine.md) | Custom Pydantic Policy Engine (not OPA) | Accepted |
| [0004](./0004-tiered-intelligence.md) | Tiered Intelligence (Deterministic → Cached → LLM) | Accepted |
| [0005](./0005-three-layer-idempotency.md) | Three-Layer Idempotency (HTTP / Command / Gateway) | Accepted |
