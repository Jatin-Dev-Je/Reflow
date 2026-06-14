# Reflow

**Trustworthy Autonomous Payment Recovery Platform.**

Every failed payment should be investigated, explained, and recovered automatically — with verifiable evidence, policy-enforced execution, and zero double-charge risk.

Reflow is an agentic payment operations platform that continuously analyzes transaction failures, determines recoverable opportunities, executes safe recovery actions, and provides complete auditability for every decision.

---

## Why Reflow

Most retry systems rely on static rules. They cannot answer:

- Why did the payment fail?
- Is it recoverable?
- What is the best recovery strategy?
- How confident are we?
- What evidence supports the decision?
- Can the action be safely executed?

Reflow answers all of these — with citations.

## Core Guarantees

- **Evidence-based decisions** — no agent acts without grounded evidence
- **Decision provenance** — every action traceable end-to-end
- **Idempotent execution** — zero double charges
- **Event sourcing** — immutable cryptographically-chained audit trail
- **Policy enforcement** — agents propose, policies decide
- **Human-in-the-loop** — critical actions require approval
- **Red-team hardened** — survives retry storms, replay attacks, prompt injection

## Architecture (high level)

```
Transaction Events
   ↓
Event Ingestion → Feature & Evidence Engine → Health Intelligence
   ↓
Diagnosis Agent → Strategy Agent → Risk Agent → Guard Agent
   ↓
Policy Engine → Execution Engine → Recovery Outcome Tracking
   ↓
Learning Loop
```

## Repo Layout

```
reflow/
├── backend/    # FastAPI + Pydantic AI + Postgres + Redis
└── frontend/   # (coming) Next.js + shadcn/ui + Recharts + Socket.io
```

See [`backend/README.md`](./backend/README.md) for the backend stack and architecture.

## Status

Early-stage. Backend scaffolding in place. Implementation underway.

## License

See [LICENSE](./LICENSE).
