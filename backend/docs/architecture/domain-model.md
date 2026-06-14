# Reflow — Domain Model & Schema Map

Maps every bounded context to its aggregates, events, and database tables.
The authoritative DDL is in `backend/migrations/sql/001_initial_schema.sql`.

---

## Aggregates at a glance

| Aggregate | Stream type | Identity | Owns | Read model table |
|---|---|---|---|---|
| **Transaction** | `transaction-<id>` | `txn.transactions.id` | Attempts, status, customer ref | `txn.transactions`, `txn.attempts` |
| **Recovery** | `recovery-<id>` | `recovery.recoveries.id` | Saga state, execution attempts | `recovery.recoveries`, `recovery.steps`, `recovery.execution_attempts` |
| **Diagnosis** | `diagnosis-<id>` | `agent.diagnoses.id` | Root cause + evidence | `agent.diagnoses`, `agent.evidence_items` |
| **Strategy** | `strategy-<id>` | `agent.strategies.id` | Action proposal | `agent.strategies` |
| **Risk Assessment** | `risk-<id>` | `agent.risk_assessments.id` | Multi-dimension scores | `agent.risk_assessments` |
| **Policy** | `policy-<id>` | `policy.policies.id` | Versioned rule sets | `policy.policies`, `policy.policy_versions` |
| **Approval Request** | `approval-<id>` | `recovery.approval_requests.id` | HITL workflow | `recovery.approval_requests` |

All aggregates are persisted as events in `audit.events` and projected into the read tables above.

---

## Event catalog (initial)

Each event has `event_type`, `schema_version`, and a JSONB `payload` validated by a Pydantic model.

### Transaction stream
- `TransactionCreated` — first time we see a transaction
- `PaymentFailed` — terminal failure of an attempt
- `RetryAttempted` — gateway call made
- `RetrySucceeded`
- `RetryFailed`
- `PaymentRecovered` — terminal success
- `PaymentAbandoned`

### Recovery stream (the saga)
- `RecoveryCreated`
- `DiagnosisGenerated` — references diagnosis_id
- `StrategyProposed` — references strategy_id
- `RiskAssessed` — references risk_assessment_id
- `PolicyDecided` — allow / deny / require_approval, references policy_decision_id
- `ApprovalRequested` — references approval_id
- `ApprovalGranted` / `ApprovalRejected` / `ApprovalExpired`
- `ExecutionAttempted` — references execution_attempt_id
- `ExecutionSucceeded`
- `ExecutionFailed`
- `CompensationStarted`
- `CompensationCompleted`
- `RecoveryCompleted` — terminal: recovered / failed / abandoned

### Diagnosis stream
- `DiagnosisRequested`
- `EvidenceCollected`
- `DiagnosisCompleted`

### Strategy stream
- `StrategyRequested`
- `StrategyCompleted`

### Risk stream
- `RiskAssessmentRequested`
- `RiskAssessmentCompleted`

### Policy stream
- `PolicyVersionCreated`
- `PolicyVersionActivated`
- `PolicyVersionRetired`

### Health stream (not aggregate-scoped; written by health worker)
- `GatewayHealthSampled`
- `GatewayOutageDetected` / `GatewayOutageEnded`
- `IssuerOutageDetected` / `IssuerOutageEnded`

---

## Schema map by bounded context

### `core` — identity, tenancy, auth, HTTP idempotency

```
core.tenants                ─ a merchant
core.tenant_settings        ─ per-merchant config (retry limits, thresholds, LLM budget)
core.users                  ─ humans
core.user_tenant_roles      ─ many-to-many with role
core.api_keys               ─ API credentials, hashed
core.idempotency_keys       ─ HTTP-level (24h TTL)
```

### `audit` — event store, snapshots, outbox, chain

```
audit.events                ─ append-only, hash-chained, immutable (UPDATE/DELETE blocked by trigger)
audit.snapshots             ─ aggregate snapshots every 50 events
audit.outbox                ─ transactional outbox → Redis Streams
audit.event_subscriptions   ─ consumer offsets per projection
audit.chain_anchors         ─ signed Merkle roots, published periodically
```

**Why immutable**: the event store is the source of truth and the evidence base for every audit query. Any UPDATE would break the cryptographic chain.

### `txn` — transactions & attempts (read model)

```
txn.transactions            ─ one row per business transaction (idempotent on tenant_id, external_id)
txn.attempts                ─ one row per charge attempt; UNIQUE(transaction_id, attempt_number)
```

**No PAN, no CVV.** Only BIN (first 6) + last4 + brand + funding + country. PCI scope minimized.

### `agent` — diagnosis, strategy, risk outputs

```
agent.diagnoses             ─ root cause + confidence + LLM provenance
agent.evidence_items        ─ citations [1], [2], [3]... each replayable via source_query
agent.strategies            ─ proposed action with expected probability + revenue
agent.risk_assessments      ─ 4 scores + overall level + factors JSONB
```

**Citation contract**: every diagnosis has ≥1 evidence_item. Trust View displays `observation` text alongside the diagnosis narrative.

### `policy` — versioned rules + decision log

```
policy.policies             ─ logical policy (one per concern, e.g. "retry limits")
policy.policy_versions      ─ versioned rule sets with content hash; only one active per policy
policy.decisions            ─ every evaluation, with full context_snapshot for replay
```

**Why context_snapshot**: any historical decision can be re-evaluated against any policy version, deterministically.

### `recovery` — the saga state machine

```
recovery.recoveries           ─ saga aggregate. UNIQUE(tenant_id, recovery_key).
recovery.steps                ─ every state transition (from/to/triggered_by/duration)
recovery.execution_attempts   ─ every gateway call. UNIQUE(gateway_id, idempotency_key) ← zero double-charge
recovery.approval_requests    ─ HITL workflow
```

**The double-charge guarantee** lives in `UNIQUE(gateway_id, idempotency_key)` on `recovery.execution_attempts`. Even if our app retries due to a network error, the DB rejects the duplicate, and the in-process layer falls back to "query the gateway and reconcile."

### `health` — gateway & issuer time-series

```
health.gateway_snapshots    ─ 1-min buckets, generated success_rate, health_score
health.issuer_snapshots     ─ same shape for issuers
health.outages              ─ detected outages with non-overlap exclusion constraint
```

The `EXCLUDE USING gist` constraint on `health.outages` prevents overlapping outages for the same subject — the data layer itself enforces the invariant.

### `intel` — memory layers

```
intel.recovery_episodes     ─ episodic memory (structured signature → outcome)
intel.recovery_patterns     ─ materialized view (aggregated success rates), refreshed every 5 min
intel.failure_embeddings    ─ semantic memory (pgvector, bge-small-en-v1.5 → 384 dim)
```

**Query patterns**:
- Episodic: indexed exact-match on `(issuer_id, gateway_id, decline_code_normalized, amount_band, time_band)`
- Pattern: matview hit via the same key (much faster than aggregating live)
- Semantic: `ORDER BY embedding <=> query_vec LIMIT 10` for fuzzy lookup

### `obs` — agent runs, LLM calls, prompts, evaluations

```
obs.prompt_templates        ─ versioned prompts. UNIQUE(name, version)
obs.agent_runs              ─ one row per agent invocation. trace_id + recovery_id correlation
obs.llm_calls               ─ one row per provider call. captures tokens, cost, latency, validation status
obs.agent_evaluations       ─ scores from golden / LLM-judge / human / rule evaluators
```

**Cost tracking is first-class**: every llm_call row has `cost_usd`. Aggregated to `agent_runs.total_cost_usd`, exposed in the Trust View.

### `flags` — feature flags + kill switches

```
flags.feature_flags         ─ global definitions
flags.tenant_flags          ─ per-tenant overrides + rollout percentage
flags.kill_switches         ─ named instant-stop levers (recovery.global, gateway.stripe, ...)
```

Every recovery start checks active kill switches. Kill-switch state is also pushed via Redis Pub/Sub so workers react in <100ms without polling.

### `sim` — benchmark runs

```
sim.runs                    ─ seeded simulation runs (config in JSONB)
sim.results                 ─ headline metrics + breakdowns by gateway/issuer/decline_code
```

`sim.runs.seed` is required — every benchmark must be reproducible.

---

## Invariants enforced at the database layer

These are not just "best effort in app code" — the database itself enforces them:

| Invariant | Enforcement |
|---|---|
| No double charge | `UNIQUE (gateway_id, idempotency_key)` on `recovery.execution_attempts` |
| One attempt number per recovery | `UNIQUE (recovery_id, attempt_number)` |
| Event store is append-only | Trigger blocks UPDATE/DELETE on `audit.events` |
| Per-stream version is monotonic | `UNIQUE (stream_id, version)` on `audit.events` |
| Per-tenant transaction uniqueness | `UNIQUE (tenant_id, external_id)` on `txn.transactions` |
| No overlapping outages for same subject | `EXCLUDE USING gist (...)` on `health.outages` |
| Active policy version is unique | `idx_policy_versions_active` partial index |
| Confidence / probability bounds | CHECK constraints (`BETWEEN 0 AND 1`) |
| Money is non-negative | CHECK `amount_cents > 0` on transactions |
| Currency is ISO 4217 | CHECK `~ '^[A-Z]{3}$'` |
| Card country is ISO 3166-1 alpha-2 | `CHAR(2)` |
| Slugs are URL-safe | CHECK regex on `core.tenants.slug` |

A senior reviewer can read the schema and immediately see *what cannot go wrong*. That is what production-grade schema design looks like.

---

## Data flow: a single payment failure to recovery

```
Webhook receives "charge.failed" from Stripe
   ↓
api/webhooks/stripe.py  → validates signature, extracts payload
   ↓
application/transactions/commands/ingest_event.py
   ├─ load Transaction aggregate (event stream)
   ├─ append PaymentFailed event   ─┐
   └─ insert outbox row             ├─ same transaction
                                    ─┘
   ↓
audit.events     +  audit.outbox  (Postgres commit)
                                    
Outbox Relay (background)
   ↓
Redis Stream "transactions"
   ↓
Recovery Worker (consumer group)
   ├─ create recovery aggregate
   ├─ persist RecoveryCreated event
   └─ enqueue diagnosis job
   ↓
Diagnosis Worker
   ├─ collect evidence (intel.recovery_patterns + health.* + intel.failure_embeddings)
   ├─ invoke DiagnosisAgent (LLM, Tier 2)
   ├─ validate output (Pydantic schema)
   ├─ insert agent.diagnoses + agent.evidence_items
   ├─ append DiagnosisGenerated event
   └─ enqueue strategy job
   ↓
   ... (strategy → risk → policy → execution) ...
   ↓
Gateway Execution
   ├─ insert recovery.execution_attempts (UNIQUE check enforces idempotency)
   ├─ call Stripe (idempotency key sent)
   ├─ persist ExecutionAttempted event
   └─ recover or fail
   ↓
recovery.recoveries.state = 'recovered'  (read model updated by event handler)
   ↓
intel.recovery_episodes ← inserted (episodic memory grows)
   ↓
Trust View projection updated
   ↓
WebSocket pushes update to subscribed dashboards
```

Every arrow is auditable. Every box is testable. Every transition is reversible (or compensable).
