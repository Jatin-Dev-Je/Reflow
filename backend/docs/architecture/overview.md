
# Reflow — Backend Architecture

> Trustworthy autonomous payment recovery. Every decision is evidence-based, policy-gated, idempotent, and cryptographically auditable.

---

## 1. Architectural Principles

These are non-negotiable. Every component must respect them.

| # | Principle | Implication |
|---|---|---|
| 1 | **No decision without evidence** | Every agent output carries grounded citations from the data layer. |
| 2 | **No execution without policy approval** | Agents propose. The Policy Engine authorizes. The Orchestrator executes. |
| 3 | **No state mutation without an event** | The event store is the source of truth. Read models are derived. |
| 4 | **No external call without idempotency** | Three-layer idempotency: HTTP, command, gateway. |
| 5 | **No process without observability** | Every span carries `tenant_id`, `trace_id`, `transaction_id`, `recovery_id`. |
| 6 | **No deploy without a kill switch** | Every new strategy / agent / gateway integration ships behind a flag. |
| 7 | **No decision is final** | Sagas are restartable. Compensations exist for every forward step. |

---

## 2. Runtime Topology

This is a **modular monolith with extraction seams** — single codebase, multiple deployable processes. Each process can later become its own service without code changes, only deployment changes.

```
                    ┌─────────────────────────────────────────┐
                    │            Edge / Ingress                │
                    │     (rate limit, auth, idempotency)      │
                    └────────────┬────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
     │   api service  │  │  ws service    │  │ webhook service│
     │   (FastAPI)    │  │  (Socket.IO)   │  │   (FastAPI)    │
     └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
             │                   │                    │
             └───────────────────┴────────────────────┘
                                 │
                                 ▼
                ┌─────────────────────────────────┐
                │       Domain + Application      │
                │   (in-process command bus)      │
                └────────────┬────────────────────┘
                             │
            ┌────────────────┼────────────────────┐
            ▼                ▼                    ▼
     ┌──────────────┐ ┌──────────────┐  ┌──────────────────┐
     │  Postgres    │ │  Redis       │  │ Event Bus        │
     │  (write +    │ │  (cache,     │  │ (Redis Streams)  │
     │   read       │ │   locks,     │  │                  │
     │   models)    │ │   queues)    │  │                  │
     └──────────────┘ └──────────────┘  └──────────┬───────┘
                                                   │
                          ┌────────────────────────┼────────────────────┐
                          ▼                        ▼                    ▼
                ┌──────────────────┐    ┌──────────────────┐  ┌──────────────────┐
                │  recovery worker │    │  diagnosis worker│  │  learning worker │
                │  (saga driver)   │    │  (LLM agents)    │  │  (drift, sims)   │
                └──────────────────┘    └──────────────────┘  └──────────────────┘
                                                   │
                                                   ▼
                                         ┌──────────────────┐
                                         │  Outbox Relay    │
                                         │  (publishes      │
                                         │   events to bus) │
                                         └──────────────────┘
```

### Process inventory

| Process | Responsibility | Scaling unit |
|---|---|---|
| `api` | HTTP REST API | Horizontal, stateless |
| `ws` | WebSocket dashboards | Sticky sessions or Redis-backed pub/sub |
| `webhook` | Inbound gateway webhooks | Horizontal, stateless |
| `recovery-worker` | Saga state machine driver | Horizontal, partitioned by `recovery_id` |
| `diagnosis-worker` | LLM agent invocations | Horizontal, rate-limited per provider |
| `learning-worker` | Drift detection, pattern refresh, embeddings | Single instance per task type |
| `outbox-relay` | Transactional outbox → event bus | Single instance (leader-elected) |
| `simulator` | 100K-transaction benchmark runner | Single instance, on-demand |

---

## 3. Communication Patterns

| Pattern | Transport | Use |
|---|---|---|
| **Sync command/query** | HTTP | API requests, admin actions |
| **Domain events** | Redis Streams | Event sourcing, cross-context choreography |
| **Pub/sub signals** | Redis Pub/Sub | Cache invalidation, kill switch propagation |
| **Real-time push** | Socket.IO over Redis adapter | Live dashboards |
| **Background jobs** | ARQ queues | Saga steps, LLM calls, projections |
| **Transactional outbox** | Postgres -> relay -> Redis Stream | Guaranteed event delivery |

### Event flow (Recovery saga)

```
PaymentFailed (gateway webhook)
    |
    v
[ Event Store ] --- outbox ---> event bus
    |
    v
RecoveryWorker reads -> creates Recovery aggregate (state=created)
    |
    v
DiagnosisAgent invoked -> DiagnosisGenerated event -> state=diagnosed
    |
    v
StrategyAgent invoked -> StrategyProposed event -> state=strategy_proposed
    |
    v
RiskAgent invoked -> RiskAssessed event -> state=risk_assessed
    |
    v
PolicyEngine evaluates -> PolicyDecided event -> state=policy_evaluated
    |
    +-- allow --------------> state=executing
    +-- require_approval --> state=awaiting_approval -> ApprovalGranted -> executing
    +-- deny --------------> state=failed (with reason)
    |
    v
GatewayExecution (idempotent) -> ExecutionAttempted event
    |
    +-- success --> PaymentRecovered -> state=recovered
    +-- failure --> retry policy -> next_action_at set OR state=failed
    +-- timeout --> compensation: query gateway -> reconcile state
```

---

## 4. Layered Code Structure

Clean / Hexagonal with DDD bounded contexts. Dependency direction: **outer depends on inner, never the reverse.**

```
+----------------------------------------------------+
|                     api/                           |  <- Transport
|              (FastAPI, WS, webhooks)               |
+----------------------+-----------------------------+
                       |
+----------------------v-----------------------------+
|                application/                        |  <- Use cases (CQRS)
|         (commands, queries, sagas)                 |
+----------+---------------+-------------------------+
           |               |
+----------v-----+  +------v--------------+
|   domain/      |  |     agents/         |  <- Business logic (pure)
| (entities,     |  | (LLM orchestrators) |
|  events,       |  |                     |
|  repo iface)   |  +---------------------+
+----------+-----+
           |
+----------v-----------------------------------------+
|              infrastructure/                       |  <- Adapters
|  (persistence, gateways, policy engine, audit log, |
|   intelligence, notifications, realtime)           |
+----------+-----------------------------------------+
           |
+----------v-----------------------------------------+
|                   core/                            |  <- Cross-cutting
|  (config, db session, redis, events, security,     |
|   observability, exceptions, middleware, types)    |
+----------------------------------------------------+
```

### Bounded contexts

| Context | Owns |
|---|---|
| `transactions` | Failed transaction lifecycle, attempts, decline taxonomy |
| `diagnosis` | Root cause analysis, evidence collection, confidence |
| `strategy` | Recovery action proposals with expected outcomes |
| `risk` | Financial / operational / customer risk scoring |
| `policy` | Rule sets, decisions, simulations |
| `recovery` | Saga state, execution attempts, outcomes |
| `health` | Gateway / issuer real-time and rolled-up health |
| `intel` | Episodic, pattern, and semantic memory |
| `audit` | Event store, cryptographic chain, provenance queries |
| `obs` | Agent runs, LLM calls, evaluations |

---

## 5. Event Sourcing — Done Properly

Not a log table. A real event-sourced system.

### Streams
- **Stream identifier**: `<aggregate_type>-<aggregate_id>` (e.g., `recovery-uuid`)
- **Stream version**: monotonic per stream, used for optimistic concurrency control
- **Global sequence**: monotonic across all streams, used for ordering and projections

### Writes
1. Load aggregate by replaying stream from snapshot (if any) + tail events
2. Execute command -> emit new events
3. Append events at `expected_version + 1`, atomic with **outbox** insert in same transaction
4. Conflict on version -> reload, retry (max 3) or surface to caller

### Snapshots
- Take snapshot every 50 events per stream
- Stored in `audit.snapshots` keyed by `(stream_id, version)`
- Replay = load latest snapshot + events with `version > snapshot.version`

### Outbox -> Event Bus
- Same DB transaction writes events + outbox rows
- **Outbox Relay** process polls `audit.outbox WHERE status='pending'` every 500ms
- Publishes to Redis Stream, marks `delivered`, retries on failure with exponential backoff
- Single relay instance (Redis-backed leader election) prevents duplicate publishes

### Event versioning
- Every event carries `schema_version`
- **Upcasters** in `core/events/upcasters.py` transform old payloads to current schema on read
- Never modify historical events; always upcast

### Projections (read models)
- Subscribers consume from Redis Streams via consumer groups
- Each projection has its own offset in `audit.event_subscriptions`
- Idempotent: every consumer tracks processed `event_id` to handle replay
- Read models in Postgres (denormalized) for fast queries

---

## 6. CQRS — Real Read Models

The Trust View, dashboards, and intelligence views are **denormalized projections**, not joins on the write store.

| Read model | Updated by | Refresh cadence |
|---|---|---|
| `transactions` (write+read) | Direct (single-aggregate) | Synchronous |
| `recovery.recoveries` (write+read) | Direct (single-aggregate) | Synchronous |
| `intel.recovery_patterns` (matview) | Periodic refresh | Every 5 min |
| `intel.failure_embeddings` | Worker on `PaymentFailed` events | Async, ~1s |
| `health.gateway_snapshots` | Worker every minute | 1-min buckets |
| Trust View payload | Pre-computed on aggregate transitions | Synchronous on state change |

---

## 7. Saga / Process Manager

Recovery is a saga with explicit states and compensations.

### State machine

```
created
  -> diagnosed
      -> strategy_proposed
          -> risk_assessed
              -> policy_evaluated
                  -> awaiting_approval -> approved -> executing
                  -> executing
                  -> failed (deny)

executing -> executed -> recovered
          -> failed
          -> compensating -> failed
```

### Driver
- `RecoveryWorker` reads `recovery.recoveries WHERE state NOT IN terminal AND next_action_at <= now()`
- Loads aggregate by replaying its stream
- Invokes state handler (one per `state` transition)
- Persists new events + outbox in single transaction
- Compensation handlers exist for every forward step (e.g., `compensate_executing` reconciles gateway state on timeout)

### Resumability
- Crash mid-saga -> worker picks up from persisted state on restart
- No in-memory saga state — everything in Postgres

---

## 8. Idempotency — Three Layers

| Layer | Key | Storage | TTL | Purpose |
|---|---|---|---|---|
| **HTTP** | `Idempotency-Key` header | `core.idempotency_keys` | 24h | Replay-safe API calls |
| **Command** | Per-command `command_id` | `audit.events` (`metadata.command_id`) | Forever | Don't process same command twice |
| **Gateway** | Generated `idempotency_key` per execution attempt | `recovery.execution_attempts` UNIQUE constraint | Forever | Zero double-charge |

### HTTP idempotency middleware
1. Extract `Idempotency-Key` (required for mutating endpoints)
2. Compute `request_hash = sha256(body)`
3. SELECT from `core.idempotency_keys`:
   - hit + matching hash -> return cached response
   - hit + different hash -> 409 Conflict
   - miss -> INSERT row, proceed, cache response on completion

### Command idempotency
- Every command carries `command_id` (UUID, set by caller or generated)
- Command handler checks if event with `metadata->>'command_id' = ?` exists for this aggregate
- If exists -> no-op, return existing outcome

### Gateway idempotency
- `execution_attempts.idempotency_key` is UNIQUE per gateway
- Generated deterministically: `sha256(recovery_id || attempt_number || gateway_id)`
- Sent to gateway as `Idempotency-Key` header (Stripe-style)

---

## 9. Resilience Patterns

### Circuit breakers
Every external dependency wrapped via decorator:

```python
@external_dependency(
    name="stripe",
    timeout_ms=2000,
    retry=Retry(attempts=3, backoff="exponential", jitter=True),
    breaker=CircuitBreaker(failure_threshold=5, recovery_timeout=30),
    bulkhead=Semaphore(concurrent=10),
    fallback=stripe_fallback,
)
async def call_stripe(...): ...
```

State: `closed -> open (on threshold) -> half_open (after timeout) -> closed (on success)`

### Per-dependency limits

| Dependency | Timeout | Retries | Concurrent |
|---|---|---|---|
| Stripe | 2s | 3 | 10 |
| Mock Gateway | 5s | 3 | 50 |
| Groq | 8s | 2 (fallback to Gemini) | 5 |
| Gemini | 10s | 2 (fallback to OpenRouter) | 3 |
| OpenRouter | 15s | 1 (no fallback) | 2 |
| Embeddings (local) | 500ms | 1 | 4 |

### Dead-letter queue
- Failed jobs after retry budget -> `audit.outbox` row with `status='dead'`
- Ops dashboard surfaces dead-lettered work for manual review

---

## 10. LLM Layer

### Tiered intelligence

| Tier | Latency | Coverage | Mechanism |
|---|---|---|---|
| **0** | <5ms | ~70% | Deterministic rules + cached decision lookup |
| **1** | <50ms | ~20% | Cached recovery patterns (Pattern Memory) |
| **2** | 500-2000ms | ~10% | Full LLM agent orchestration |

Routing rule: only escalate to Tier 2 when Tier 0 + Tier 1 return `confidence < 0.7` OR transaction value exceeds tenant's `high_value_threshold_cents`.

### LLM router

```
Primary:   Groq (Llama 3.3 70B)  - for diagnosis + strategy
Secondary: Gemini 2.0 Flash       - for risk + guard
Fallback:  OpenRouter free models - emergency
```

Routing factors: agent role, input token count, latency budget remaining in saga.

### Cost cap per decision
`max_llm_cost_per_decision = transaction_amount * tenant.llm_budget_bps / 10000`
If estimated cost exceeds cap -> use Tier 1 only, mark decision `confidence=0.5`, surface for review.

### Prompt caching
- Anthropic-style cache breakpoints in prompts (system + few-shot stable)
- Redis-side response cache keyed by `prompt_hash`
- Bypass cache for novel inputs or when freshness matters (health-aware decisions)

### Output validation
- Pydantic schema enforced via Instructor / Pydantic AI
- Validation failure -> repair attempt (max 2) -> fallback to deterministic default
- All attempts logged in `obs.llm_calls.validation_attempts`

---

## 11. Memory Architecture (6 layers)

| Layer | Storage | Purpose | Read latency |
|---|---|---|---|
| **Event Store** | Postgres (`audit.events`) | Immutable source of truth | 5-20ms |
| **Working Memory** | Redis hash, TTL=30min | In-flight saga state | <1ms |
| **Episodic Memory** | Postgres (`intel.recovery_episodes`) | Past outcomes with structured signatures | 5-20ms |
| **Pattern Memory** | Postgres matview (`intel.recovery_patterns`) | Aggregated success rates per dimension | 1-5ms |
| **Semantic Memory** | pgvector (`intel.failure_embeddings`) | Fuzzy "similar past failure" lookup | 10-50ms |
| **Health Memory** | Redis sorted sets + Postgres rollups | Time-series gateway/issuer health | <1ms (hot) / 10ms (cold) |

Agents declare memory dependencies — `DiagnosisAgent` reads from Health + Pattern + Semantic; `StrategyAgent` reads from Episodic + Pattern.

---

## 12. Policy Engine

Not OPA. Custom Pydantic-based engine — simpler, embedded, hot-reloadable.

### Model

```python
class Rule(BaseModel):
    id: str
    description: str
    when: Callable[[Context], bool]
    decide: Callable[[Context], Decision]

class Policy(BaseModel):
    id: UUID
    version: int
    rules: list[Rule]  # ordered, first match wins
```

### Evaluation
1. Load active `policy_versions` for tenant (cached in Redis, 60s TTL)
2. Iterate rules in order; first matching `when` produces decision
3. Decision = `allow | deny | require_approval`, with `reason` and `citations`
4. Persist to `policy.decisions` with `policy_version_id` and full `context_snapshot`

### Hot reload
- Policy changes write a new `policy_versions` row, `activate_at` set
- Worker invalidates Redis cache on `PolicyVersionActivated` event
- Old decisions reference their `policy_version_id` so historical audit is unambiguous

### Simulation
- Run candidate policy against last N days of `recovery.recoveries` (read-only)
- Diff: how many recoveries change decision? What's revenue impact?
- Surfaced in the Policy Editor UI before activation

---

## 13. Cryptographic Audit Log

### Per-event chain
Each event computes:
```
event_hash = sha256(
    previous_hash ||
    canonical_json(payload) ||
    canonical_json(metadata)
)
```

### Periodic anchor
- Every N events (or every M minutes), compute Merkle root over the latest range of `audit.events`
- Sign with Ed25519 private key (in env for demo; KMS for prod)
- Store in `audit.chain_anchors` with `start_sequence`, `end_sequence`, `merkle_root`, `signature`

### Verification API
- `GET /audit/verify/{event_id}` — returns Merkle inclusion proof from event up to nearest anchor
- Anyone with the public key can verify offline

### Tampering detection
- Periodic background job re-computes hashes for last 24h, alerts on mismatch

---

## 14. Multi-Tenancy

Even for v1 single-merchant demo, the model is multi-tenant from day one.

- `tenant_id` on every aggregate
- Tenant context extracted from JWT -> stored in `contextvars` -> propagated through requests and jobs
- Postgres Row-Level Security policies on all tenanted tables (enforced when `app.current_tenant_id` is set)
- Per-tenant rate limits, policies, kill switches, encryption keys (envelope encryption — future)

---

## 15. Observability Schema

Every span / log line carries:

```
{
  "trace_id": "...",
  "span_id": "...",
  "parent_span_id": "...",
  "tenant_id": "...",
  "transaction_id": "...",
  "recovery_id": "...",
  "agent_name": "...",
  "agent_run_id": "...",
  "llm_provider": "...",
  "llm_model": "...",
  "llm_cost_usd": 0.000234,
  "llm_tokens_in": 1234,
  "llm_tokens_out": 567,
  "decision_id": "...",
  "policy_version_id": "..."
}
```

### Stack
- **OpenTelemetry SDK** — traces, metrics
- **Langfuse** — LLM-specific (prompts, completions, evals, costs)
- **structlog** — JSON logs with shared context
- **Sentry** — errors

### Trace propagation
- HTTP: W3C `traceparent` header
- ARQ jobs: trace context serialized in job payload
- LLM calls: traced as child spans of agent runs
- DB queries: instrumented via SQLAlchemy events

---

## 16. Configuration & Secrets

| Concern | Mechanism |
|---|---|
| App config | Pydantic Settings, sourced from env / `.env` |
| Secrets | Env vars in dev; AWS Secrets Manager / Vault in prod (not in v1) |
| Per-tenant config | `core.tenant_settings` table |
| Policies | `policy.policy_versions` (versioned, hot-reload) |
| Feature flags | `flags.feature_flags` + `flags.tenant_flags` |
| Kill switches | `flags.kill_switches` (checked on every recovery start) |

---

## 17. Deployment Topology (target)

For v1 demo: single Docker Compose stack, all processes on one host.

For real prod (documented for clarity):
- API: 2+ instances behind load balancer
- Workers: 2+ instances per worker type, partitioned by aggregate ID
- Outbox relay: 1 instance with Postgres advisory lock for leader election
- Postgres: managed (Neon / RDS), PITR enabled, read replica for projections
- Redis: managed (Upstash / ElastiCache), cluster mode for queue scale
- Secrets: external KMS

---

## 18. Testing Strategy

| Layer | Tool | What we test |
|---|---|---|
| Unit | pytest | Domain invariants, value objects, pure functions |
| Property-based | Hypothesis | Idempotency, money arithmetic, event hashing |
| Integration | pytest + testcontainers | Repositories against real Postgres; queue workers against real Redis |
| Contract | schemathesis | API + webhook schemas don't break |
| E2E | pytest | Full saga happy paths and failure paths |
| Red-team | pytest | Retry storms, replay attacks, prompt injection, dup events, infinite loops |
| Load | Locust | 1K transactions/sec target, latency budgets |
| LLM eval | Custom harness | Golden datasets, regression, drift |

---

## 19. What Is Explicitly NOT Yet Built

Being honest with the audit trail. These are documented gaps with planned closure:

| Gap | When |
|---|---|
| Real multi-tenant RLS policies (table-level only for now) | Phase 2 |
| KMS-backed signing for audit chain | Production |
| Cross-region replication for events | Production |
| Snapshot compaction job | Phase 2 |
| Real gateway integrations beyond Stripe test mode | Per partner |
| SOC 2 / PCI scope documentation | Pre-launch |
