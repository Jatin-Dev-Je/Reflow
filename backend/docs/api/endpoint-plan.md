# Reflow Backend — Endpoint Plan

~108 endpoints across the product lifecycle. **MVP slice = ~45** (marked ⭐).

The single most important endpoint is `GET /transactions/{id}/timeline` — the Trust View payload. It returns the entire decision chain (events → diagnosis → strategy → risk → policy → execution → outcome with all citations resolved) in one round-trip. Build this first.

---

## Auth — `/api/v1/auth`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 1 | POST | `/auth/register` | Create user + first tenant | |
| 2 | POST | `/auth/login` | Issue access + refresh JWT | ⭐ |
| 3 | POST | `/auth/refresh` | Refresh access token | ⭐ |
| 4 | POST | `/auth/logout` | Revoke refresh token | |
| 5 | POST | `/auth/forgot-password` | Email reset link | |
| 6 | POST | `/auth/reset-password` | Apply password reset | |
| 7 | POST | `/auth/verify-email` | Confirm email | |
| 8 | GET | `/auth/me` | Current user + tenant + roles | ⭐ |

## Tenants & Members — `/api/v1/tenants`, `/users`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 9 | GET | `/tenants/current` | Current tenant info | ⭐ |
| 10 | PATCH | `/tenants/current` | Update tenant metadata | |
| 11 | GET | `/tenants/current/settings` | Recovery + LLM budget settings | ⭐ |
| 12 | PATCH | `/tenants/current/settings` | Update settings | |
| 13 | GET | `/users` | List members | |
| 14 | POST | `/users/invite` | Invite member | |
| 15 | PATCH | `/users/{id}/role` | Change role | |
| 16 | DELETE | `/users/{id}` | Revoke membership | |

## API Keys — `/api/v1/api-keys`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 17 | GET | `/api-keys` | List | |
| 18 | POST | `/api-keys` | Create — full key returned once | |
| 19 | DELETE | `/api-keys/{id}` | Revoke | |
| 20 | POST | `/api-keys/{id}/rotate` | Rotate (returns new key) | |

## Transactions — `/api/v1/transactions` ⭐ core

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 21 | POST | `/transactions` | Manual ingest (rare — most come via webhook) | |
| 22 | GET | `/transactions` | List + filters + pagination | ⭐ |
| 23 | GET | `/transactions/{id}` | Full detail | ⭐ |
| 24 | GET | `/transactions/{id}/attempts` | Charge attempts | ⭐ |
| 25 | GET | `/transactions/{id}/timeline` | **Trust View** — full chain | ⭐⭐ |
| 26 | GET | `/transactions/stats` | Aggregates | ⭐ |

## Webhooks — `/api/webhooks` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 27 | POST | `/webhooks/stripe` | Stripe events (signature verified) | ⭐ |
| 28 | POST | `/webhooks/mock-gateway` | Mock gateway (simulation) | ⭐ |
| 29 | POST | `/webhooks/gateway/{provider}` | Other providers | |

## Diagnoses — `/api/v1/diagnoses`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 30 | GET | `/diagnoses` | List | ⭐ |
| 31 | GET | `/diagnoses/{id}` | Diagnosis + evidence | ⭐ |
| 32 | GET | `/diagnoses/{id}/evidence` | Just the citations | |
| 33 | POST | `/diagnoses/replay` | Re-run with current logic (debugging) | |

## Strategies — `/api/v1/strategies`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 34 | GET | `/strategies` | List | |
| 35 | GET | `/strategies/{id}` | Single strategy | |

## Risk Assessments — `/api/v1/risk-assessments`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 36 | GET | `/risk-assessments/{id}` | Scores + factors | |

## Recoveries — `/api/v1/recoveries` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 37 | POST | `/recoveries` | Manually start | |
| 38 | GET | `/recoveries` | List + filter by state | ⭐ |
| 39 | GET | `/recoveries/{id}` | Full saga state | ⭐ |
| 40 | GET | `/recoveries/{id}/steps` | Step history | ⭐ |
| 41 | GET | `/recoveries/{id}/executions` | Gateway calls | |
| 42 | POST | `/recoveries/{id}/cancel` | Cancel in-flight | |
| 43 | POST | `/recoveries/{id}/retry` | Manual retry | |
| 44 | GET | `/recoveries/stats` | Aggregates | ⭐ |

## Approvals — `/api/v1/approvals` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 45 | GET | `/approvals` | Pending queue | ⭐ |
| 46 | GET | `/approvals/{id}` | Single approval | ⭐ |
| 47 | POST | `/approvals/{id}/approve` | Grant | ⭐ |
| 48 | POST | `/approvals/{id}/reject` | Reject | ⭐ |

## Policies — `/api/v1/policies` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 49 | GET | `/policies` | List | ⭐ |
| 50 | POST | `/policies` | Create new policy | |
| 51 | GET | `/policies/{id}` | Single | ⭐ |
| 52 | PATCH | `/policies/{id}` | Edit metadata | |
| 53 | DELETE | `/policies/{id}` | Retire | |
| 54 | GET | `/policies/{id}/versions` | Version history | ⭐ |
| 55 | POST | `/policies/{id}/versions` | New draft version | |
| 56 | POST | `/policies/{id}/versions/{v}/activate` | Activate version | |
| 57 | POST | `/policies/{id}/versions/{v}/simulate` | Diff vs historical recoveries | ⭐ |
| 58 | GET | `/policies/decisions` | Decision log | ⭐ |
| 59 | GET | `/policies/decisions/{id}` | Single decision + context replay | ⭐ |

## Health Intelligence — `/api/v1/health-intel`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 60 | GET | `/health-intel/gateways` | All gateway scores | ⭐ |
| 61 | GET | `/health-intel/gateways/{id}` | Single | |
| 62 | GET | `/health-intel/gateways/{id}/timeseries` | History | ⭐ |
| 63 | GET | `/health-intel/issuers` | All issuer scores | ⭐ |
| 64 | GET | `/health-intel/issuers/{id}` | Single | |
| 65 | GET | `/health-intel/issuers/{id}/timeseries` | History | |
| 66 | GET | `/health-intel/outages` | Active outages | |
| 67 | GET | `/health-intel/outages/history` | Past outages | |

## Recovery Intelligence — `/api/v1/intel`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 68 | GET | `/intel/patterns` | Success-rate lookup table | |
| 69 | GET | `/intel/patterns/lookup` | Query specific signature | |
| 70 | GET | `/intel/episodes` | Recent episodic memory | |
| 71 | GET | `/intel/similar` | Semantic similarity search | |
| 72 | GET | `/intel/drift` | Drift detection report | |

## Audit — `/api/v1/audit` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 73 | GET | `/audit/events` | Event store query | ⭐ |
| 74 | GET | `/audit/events/{id}` | Single event | ⭐ |
| 75 | GET | `/audit/streams/{stream_id}` | All events for an aggregate | ⭐ |
| 76 | GET | `/audit/verify/{event_id}` | Merkle inclusion proof | ⭐ |
| 77 | GET | `/audit/anchors` | Signed chain anchors | |
| 78 | GET | `/audit/anchors/latest` | Most recent anchor | |

## Simulation — `/api/v1/simulations` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 79 | POST | `/simulations` | Start a run | ⭐ |
| 80 | GET | `/simulations` | List | ⭐ |
| 81 | GET | `/simulations/{id}` | Run status | ⭐ |
| 82 | GET | `/simulations/{id}/results` | Headline metrics + breakdowns | ⭐ |
| 83 | POST | `/simulations/{id}/cancel` | Cancel | |
| 84 | GET | `/simulations/benchmarks` | Compare across runs | ⭐ |

## Dashboard — `/api/v1/dashboard` ⭐

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 85 | GET | `/dashboard/executive` | KPIs: success rate, revenue, recovery | ⭐ |
| 86 | GET | `/dashboard/operations` | Live counters | |
| 87 | GET | `/dashboard/trust` | Compliance metrics | |

## Feature Flags / Kill Switches — `/api/v1/flags`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 88 | GET | `/flags` | List flag values for tenant | |
| 89 | PUT | `/flags/{key}` | Set tenant override | |
| 90 | GET | `/flags/kill-switches` | List kill switches | |
| 91 | POST | `/flags/kill-switches/{key}/activate` | Stop! | |
| 92 | POST | `/flags/kill-switches/{key}/deactivate` | Resume | |

## LLM Observability — `/api/v1/observability`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 93 | GET | `/observability/agent-runs` | List | |
| 94 | GET | `/observability/agent-runs/{id}` | Single run with LLM calls | |
| 95 | GET | `/observability/llm-calls` | LLM-level detail | |
| 96 | GET | `/observability/llm-calls/{id}` | Single | |
| 97 | GET | `/observability/costs` | Cost breakdowns | |
| 98 | GET | `/observability/prompts` | Prompt templates | |
| 99 | POST | `/observability/prompts` | New version | |
| 100 | GET | `/observability/evaluations` | Eval results | |

## System — `/api/v1/system`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 101 | GET | `/system/info` | Version, build, env | ⭐ |
| 102 | GET | `/system/config` | Sanitized config snapshot | |

## WebSocket — `/ws` ⭐

| # | Path | Channel | MVP |
|---|---|---|---|
| 103 | `/ws/transactions` | Live transaction stream | ⭐ |
| 104 | `/ws/recoveries` | Live recovery state changes | ⭐ |
| 105 | `/ws/health` | Live gateway/issuer health | ⭐ |
| 106 | `/ws/approvals` | New approval notifications | ⭐ |

## Health — `/`

| # | Method | Path | Purpose | MVP |
|---|---|---|---|---|
| 107 | GET | `/healthz` | Liveness | ⭐ |
| 108 | GET | `/readyz` | Readiness | ⭐ |

---

## Implementation order

1. **Health + Auth + Webhooks + Transactions list/get/timeline** — see one real transaction end-to-end
2. **Recoveries list/get/steps + Approvals** — the saga visualisation
3. **Audit events + verify** — prove the chain
4. **Policies + decisions + simulate** — the trust story
5. **Simulation harness + benchmarks** — the 100K-transaction proof
6. **Dashboard + WebSocket** — the live experience
7. **Health Intelligence + Recovery Intelligence + LLM Observability** — the depth
8. **Feature flags + Admin + System** — operational tooling

Each endpoint follows the same shape: `routes.py` (FastAPI route) → `application/<context>/commands|queries/*.py` (use case) → domain + infrastructure.
