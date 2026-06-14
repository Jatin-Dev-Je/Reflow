# 0004 — Tiered Intelligence (Deterministic → Cached → LLM)

**Status:** Accepted
**Date:** 2026-06-14

## Context

Reflow's "AI agents" must make recovery decisions, but:

- Every transaction failure cannot afford a 500-2000ms LLM call
- LLM cost per decision must stay below the merchant's per-transaction LLM budget
- Decisions must be deterministic and replayable when possible
- For novel or high-stakes failures, full agent reasoning *is* required

A blanket "always call the LLM" approach blows latency, cost, and explainability budgets. A blanket "never call the LLM" approach loses the qualitative judgment LLMs are good at.

## Decision

A **three-tier intelligence pipeline** that escalates only when needed.

| Tier | Mechanism | Latency | Cost | Coverage |
|---|---|---|---|---|
| **Tier 0** | Deterministic rules + Redis-cached decisions | <5 ms | $0 | ~70% |
| **Tier 1** | Pattern Memory lookup (`intel.recovery_patterns` matview) | <50 ms | $0 | ~20% |
| **Tier 2** | Full LLM agent orchestration | 500-2000 ms | $0.001-0.02 | ~10% |

### Escalation rules

- **Tier 0 → Tier 1**: if no deterministic rule matches OR rule returns `confidence < 0.7`
- **Tier 1 → Tier 2**: if pattern memory has no signature match OR matched pattern has `total_count < 50` OR transaction value exceeds `tenant_settings.high_value_threshold_cents`

### Cost gating for Tier 2

`max_llm_cost = transaction_amount * tenant.llm_budget_bps / 10000`

If estimated LLM cost (estimated by token count × model price) exceeds this cap:
- Fall back to Tier 1 with `confidence=0.5`
- Surface for human review via approval queue

### Provenance

Every recovery records which tier produced the decision in `recovery.recoveries.metadata.intelligence_tier`. Tier 2 calls are linked to `obs.agent_runs` and `obs.llm_calls` for full cost / token accounting.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **LLM-only (Tier 2 for everything)** | Cost: $0.01 × millions of transactions = unworkable; latency budget blown |
| **Rules-only (Tier 0 for everything)** | Can't handle novel failure patterns; misses recovery opportunities |
| **Single ML model trained from outcomes** | Doesn't explain itself; can't cite evidence; cold-start problem |
| **LLM for everything but with aggressive caching** | Cache misses on novel inputs still blow latency; cache key design is itself a hard problem |

## Consequences

**Easier:**
- ~95% of decisions are sub-50ms and $0 — gross margin works
- LLM is reserved for high-judgment cases where it's actually useful
- Every decision has clear provenance (which tier, why escalated)
- Cost cap protects against runaway LLM spend per merchant

**Harder:**
- Three code paths instead of one
- Tier 0 rule maintenance: as failure modes evolve, rules must too
- Confidence thresholds are tuning parameters — need ongoing eval

**Mitigations:**
- `agents/orchestrator/coordinator.py` is the **single** entry point that handles tier selection; downstream code is tier-agnostic
- Tier 0 rules are themselves expressed in the same Pydantic policy DSL — same testing infrastructure as Policy Engine
- Confidence thresholds are stored in `core.tenant_settings.feature_flags`, hot-reloadable
- Eval harness in `obs.agent_evaluations` tracks tier outcomes; regression alarms surface drift

## Notes

The Tier 1 → Tier 2 escalation is the most important boundary. Underescalating misses recoveries; overescalating burns cost. The eval harness must continuously monitor escalation decisions and the cost of false negatives (Tier 1 said "go" but LLM would have said "stop").
