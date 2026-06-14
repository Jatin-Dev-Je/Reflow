# 0002 — Event Sourcing with Transactional Outbox

**Status:** Accepted
**Date:** 2026-06-14

## Context

Reflow is a payments platform. Three non-negotiable requirements drive persistence:

1. **Auditability** — every decision must be reconstructable, cryptographically verifiable, and replayable months later
2. **Zero double charge** — even under arbitrary partial failures, network retries, and crashes
3. **Evidence-based decisions** — agents need to query historical outcomes, patterns, and time-series state

A state-based ORM with `UPDATE` semantics cannot satisfy (1). A simple log-table-as-history cannot satisfy (3) at query speed. We need both.

## Decision

Use **event sourcing as the write side** and **CQRS-style projections as the read side**, connected by a **transactional outbox**.

### Write side

- All state changes are emitted as **events** appended to `audit.events`
- Each aggregate has a **stream** keyed by `<stream_type>-<aggregate_id>`
- Each stream has a monotonic **version** for optimistic concurrency control
- The global table also tracks a **global_sequence** for cross-stream ordering
- Events carry a **cryptographic chain**: `event_hash = sha256(previous_hash || payload || metadata)`
- **Snapshots** every 50 events bound replay cost

### Outbox

- In the same DB transaction as the event insert, write a row to `audit.outbox`
- An **Outbox Relay** process polls pending rows and publishes to Redis Streams
- This gives **at-least-once delivery** with no dual-write inconsistency
- Consumers track offsets in `audit.event_subscriptions` and dedupe by `event_id`

### Read side

- Subscribers consume from Redis Streams via consumer groups
- They write to **denormalized read models** in Postgres (the `txn.*`, `recovery.*`, etc. tables)
- Read models are eventually consistent; the Trust View shows a "last updated" timestamp
- For single-aggregate views (a transaction, a recovery), the read model is updated synchronously in the same transaction as the event insert

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **State-based ORM with audit columns** | Can't replay decisions; can't prove no tampering |
| **Event log without snapshots** | Stream replay grows linearly forever; reads become unbounded |
| **Kafka instead of Redis Streams** | Operational overhead too high for free-tier demo; Redis Streams give us consumer groups, replay, and acks |
| **Listen/notify instead of outbox** | Loses events if no listener is connected; no replay |
| **CDC from Postgres (Debezium)** | Heavy infra; tightly couples consumers to physical table layout |
| **EventStoreDB** | Yet another stateful service; Postgres + outbox covers our needs |

## Consequences

**Easier:**
- Full audit replayability for any historical decision
- Cryptographic tamper-evidence built in
- Time-travel debugging: re-run a saga with the data available at any past timestamp
- Adding new read models is mechanical: write a new projection, replay events into it

**Harder:**
- Event schema evolution requires upcasters — never modify historical events
- Read-after-write needs care: caller must wait for projection or read from write model
- Outbox Relay needs leader election to avoid duplicate publishes (Postgres advisory lock)
- Engineers must learn the "events, not updates" mental model

**Mitigations:**
- `core/events/upcasters.py` is the single, tested location for schema migration
- Single-aggregate read models update synchronously, avoiding read-after-write surprises on the hot path
- Outbox Relay uses a Postgres advisory lock keyed by `'outbox-relay'` — only one process holds it
- Architecture tests assert that **no** code path modifies aggregate state without appending an event
