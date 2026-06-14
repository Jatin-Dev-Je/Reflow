# 0003 — Custom Pydantic Policy Engine (not OPA)

**Status:** Accepted
**Date:** 2026-06-14

## Context

Every recovery action must pass a policy check before execution. Policies encode hard constraints (max retries, retry window, high-value approval thresholds, blocked routes) and soft signals (preferences, suggestions). Three properties matter:

1. **Auditability** — every decision logs which rule fired and why
2. **Hot reload** — operators must change policies without a deploy
3. **Simulation** — before activating a new policy, show its impact on historical recoveries

The policy engine is on the hot path of every recovery, so latency matters too (target: p99 < 10ms).

## Decision

Build a **custom Pydantic-based policy engine** rather than adopting OPA, Cedar, or Oso.

### Shape

```python
class Rule(BaseModel):
    id: str
    description: str
    when:   Callable[[PolicyContext], bool]
    decide: Callable[[PolicyContext], Decision]

class Policy(BaseModel):
    id: UUID
    version: int
    rules: list[Rule]  # ordered, first match wins
```

### Storage

- `policy.policies` — logical policy (one row per concern)
- `policy.policy_versions` — versioned, content-hashed; only one active per policy
- `policy.decisions` — every evaluation with full `context_snapshot` for replay

### Evaluation

1. Load active versions for tenant (cached in Redis, 60s TTL, invalidated on `PolicyVersionActivated` event)
2. Iterate rules in order; first `when` that matches produces the `Decision`
3. Persist the decision with `policy_version_id` so historical reads are unambiguous

### Hot reload & simulation

- Editing a policy creates a new `policy_versions` row in `draft` state
- "Simulate" button replays last N days of recoveries against the draft, surfaces diff
- "Activate" sets `activated_at`; Redis cache invalidated via Pub/Sub

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **OPA (Rego)** | Powerful but adds a sidecar, separate language, separate eval engine; overkill for our rules; harder to test in Python |
| **Cedar** | Newer than OPA, fewer Python bindings, similar overkill |
| **Oso** | Tightly coupled to its own permission model; awkward for hot-reload |
| **Database-stored SQL rules** | Hard to express compound conditions; can't simulate against future state |
| **Hardcoded Python** | No hot reload; no per-tenant variation; no audit trail of policy edits |

## Consequences

**Easier:**
- Policy authors are the same engineers writing the rest of the code — no new language
- Policies are unit-testable like any other Python function
- Simulation is just "instantiate the candidate policy, run it against persisted contexts"
- Latency is trivial (Python function calls, in-process)
- Schema migrations to policy shape are caught by Pydantic at load time

**Harder:**
- Non-engineers can't author policies directly (rule editing UI must serialize to safe DSL or Python AST)
- Code-as-policy means policy review = code review (slower for trivial changes)
- We own the safety: no sandboxing of rule functions

**Mitigations:**
- The policy editor UI emits a **restricted DSL** stored as JSON in `policy_versions.rules`, which is compiled to safe `Rule` functions server-side — non-engineers never touch raw Python
- The DSL only supports a curated set of predicates over `PolicyContext` fields; unsafe operations (file I/O, network) are unreachable
- Every policy version stores its `rules_hash`; any tampering is detected by the chain anchor process

## Notes

If we later need OPA-style policy-as-data with cross-organization sharing, we can swap the engine while keeping the database tables and decision log unchanged.
