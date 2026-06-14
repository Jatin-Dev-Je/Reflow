# 0005 — Three-Layer Idempotency (HTTP / Command / Gateway)

**Status:** Accepted
**Date:** 2026-06-14

## Context

Zero double charges is a non-negotiable product requirement. Failure modes that *can* cause duplicate charges if unmanaged:

1. **HTTP layer**: client retries on network timeout — request was received and processed, response was lost
2. **Command layer**: same logical action enqueued twice (e.g., two webhook deliveries of the same event)
3. **Gateway layer**: our app retries a gateway call that actually succeeded the first time

A single idempotency mechanism cannot cover all three layers because the keys, scopes, and storage lifetimes differ. We need explicit handling at each.

## Decision

Three independent idempotency layers, each with its own key, store, and TTL.

### Layer 1: HTTP Idempotency

**Key**: client-supplied `Idempotency-Key` header
**Scope**: per (tenant, key)
**Storage**: `core.idempotency_keys` table
**TTL**: 24 hours
**Mechanism**:
1. Middleware computes `request_hash = sha256(canonical(body))`
2. Looks up `(tenant_id, idempotency_key)`:
   - Miss → insert row with `state='in_flight'`, proceed
   - Hit + `state='in_flight'` + same hash → 409 Conflict (concurrent retry)
   - Hit + `state='completed'` + same hash → return cached response
   - Hit + different hash → 422 Unprocessable Entity (key reuse with different payload)
3. On completion, update row with response + `state='completed'`

### Layer 2: Command Idempotency

**Key**: `command_id` (UUID, set by caller or auto-generated)
**Scope**: per aggregate
**Storage**: `audit.events.metadata->>'command_id'` — indexed
**TTL**: forever
**Mechanism**:
1. Command handler loads the aggregate's event stream
2. Checks if any prior event has `metadata.command_id == this_command_id`
3. If yes → no-op, return existing outcome from event
4. If no → execute, append new event with `metadata.command_id`

This handles the case where the same command is dispatched twice (e.g., two consumers of the same Redis Stream message, or a retried webhook).

### Layer 3: Gateway Idempotency

**Key**: deterministic per execution attempt: `sha256(recovery_id || attempt_number || gateway_id)`
**Scope**: per gateway
**Storage**: `recovery.execution_attempts.idempotency_key` with `UNIQUE (gateway_id, idempotency_key)` constraint
**TTL**: forever
**Mechanism**:
1. Before calling the gateway, insert the row with the key
2. If unique violation → another execution already happened or is in flight; load existing row, reconcile state from gateway if needed
3. If insert succeeds → send to gateway with same key as the gateway's native idempotency header (Stripe-style `Idempotency-Key`)
4. The gateway itself prevents duplicate charges using the same key

This is **the database-enforced guarantee** that no charge can happen twice — even if our app crashes between the row insert and the gateway call, the next retry will find the row and reconcile.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **HTTP layer only** | Doesn't protect against duplicate webhooks or duplicate queue messages |
| **Gateway layer only** | Forces all calls to round-trip the gateway just to dedupe; expensive and slow |
| **Single key passed through all layers** | Layer responsibilities differ; coupling them creates leaky abstractions |
| **App-managed mutex (Redis lock)** | Locks are about *exclusion*, not idempotency; doesn't handle "I already did this" |

## Consequences

**Easier:**
- Each layer has a clear, single responsibility
- Failure mode analysis is straightforward: trace which layer would have caught a given duplicate
- The DB constraint on `(gateway_id, idempotency_key)` is the **final, undefeatable** safeguard
- Replay of historical events is safe — command idempotency dedupes by `command_id`

**Harder:**
- Three different stores to reason about
- HTTP idempotency keys must be supplied by clients; SDK or docs must enforce this
- Reconciliation on duplicate gateway insert needs robust "query gateway and infer state" logic

**Mitigations:**
- Middleware automatically requires `Idempotency-Key` for all mutating endpoints — returns 400 if missing
- The SDK we publish for merchants generates idempotency keys by default
- Gateway reconciliation logic lives in `infrastructure/gateways/<provider>/reconciler.py` — one file, one responsibility, well-tested
- Red-team tests in `tests/red_team/replay_attack_test.py` and `duplicate_event_test.py` continuously assert that no path can produce a double charge

## Notes

The order of the three layers is intentional — outermost (HTTP) first, innermost (Gateway) last. By the time a request reaches the gateway, three independent checks have run. Any one of them is sufficient to prevent a double charge; together they are belt, suspenders, and a load-bearing safety harness.
