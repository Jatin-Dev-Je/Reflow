-- =============================================================================
-- Reflow — Initial Schema (v1)
-- =============================================================================
-- PostgreSQL 16+
--
-- Design principles:
--   1. Multi-tenant from day one (tenant_id everywhere)
--   2. Event-sourced core (audit.events is source of truth)
--   3. Append-only audit, immutable history
--   4. Three-layer idempotency (HTTP, command, gateway)
--   5. Cryptographic chain over events (hash + Merkle anchors)
--   6. Denormalized read models for hot queries (Trust View, dashboards)
--   7. pgvector for semantic memory; matviews for pattern memory
--   8. JSONB for evolving payloads, with strict typing at app layer
--   9. Time-series tables bucketed for cheap rollups
--  10. UNIQUE constraints enforce business invariants (no double charges)
--
-- Schemas:
--   core   — tenants, users, auth, idempotency
--   txn    — transactions, attempts
--   agent  — diagnosis, strategy, risk outputs
--   policy — policies, versions, decisions
--   recovery — saga state, steps, execution attempts, approvals
--   health — gateway / issuer health time-series
--   intel  — episodic, pattern, semantic memory
--   audit  — event store, snapshots, outbox, chain anchors
--   obs    — agent runs, LLM calls, prompt templates, evaluations
--   sim    — simulation runs and results
--   flags  — feature flags, kill switches
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid(), digest()
CREATE EXTENSION IF NOT EXISTS citext;       -- case-insensitive emails
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- exclusion constraints, time ranges
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings

-- -----------------------------------------------------------------------------
-- Schemas
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS txn;
CREATE SCHEMA IF NOT EXISTS agent;
CREATE SCHEMA IF NOT EXISTS policy;
CREATE SCHEMA IF NOT EXISTS recovery;
CREATE SCHEMA IF NOT EXISTS health;
CREATE SCHEMA IF NOT EXISTS intel;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS obs;
CREATE SCHEMA IF NOT EXISTS sim;
CREATE SCHEMA IF NOT EXISTS flags;

-- -----------------------------------------------------------------------------
-- Conventions
-- -----------------------------------------------------------------------------
-- * All ids: UUID v4 (gen_random_uuid). Future: switch to UUID v7 for time-ordering.
-- * All money: BIGINT cents in a single currency per row (ISO 4217 code stored).
-- * All timestamps: TIMESTAMPTZ in UTC.
-- * created_at / updated_at on mutable tables; updated_at maintained by trigger.
-- * No ON DELETE CASCADE on audit/event tables — never delete history.
-- * tenant_id on every tenant-scoped table for RLS readiness.
-- * Indexes named explicitly; partial indexes for hot subsets.
-- -----------------------------------------------------------------------------

-- Generic updated_at trigger
CREATE OR REPLACE FUNCTION core.set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- core: tenants, users, auth, idempotency
-- =============================================================================

CREATE TABLE core.tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$'),
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','suspended','archived')),
    tier        TEXT NOT NULL DEFAULT 'standard'
                CHECK (tier IN ('standard','priority','enterprise')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_tenants_updated_at BEFORE UPDATE ON core.tenants
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TABLE core.tenant_settings (
    tenant_id                   UUID PRIMARY KEY
                                REFERENCES core.tenants(id) ON DELETE CASCADE,
    default_currency            CHAR(3) NOT NULL DEFAULT 'USD'
                                CHECK (default_currency ~ '^[A-Z]{3}$'),
    max_retries_per_txn         SMALLINT NOT NULL DEFAULT 3 CHECK (max_retries_per_txn BETWEEN 0 AND 10),
    retry_window_hours          SMALLINT NOT NULL DEFAULT 24 CHECK (retry_window_hours BETWEEN 1 AND 168),
    high_value_threshold_cents  BIGINT  NOT NULL DEFAULT 5000000,    -- $50K
    hitl_required_above_cents   BIGINT  NOT NULL DEFAULT 100000000,  -- $1M
    llm_budget_bps              INT     NOT NULL DEFAULT 50          -- 0.5% of txn
                                CHECK (llm_budget_bps BETWEEN 0 AND 10000),
    embargo_until               TIMESTAMPTZ,                          -- block all recovery until
    feature_flags               JSONB   NOT NULL DEFAULT '{}'::jsonb,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_tenant_settings_updated_at BEFORE UPDATE ON core.tenant_settings
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TABLE core.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT NOT NULL UNIQUE,
    hashed_password TEXT,
    display_name    TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_superuser    BOOLEAN NOT NULL DEFAULT false,
    mfa_secret      TEXT,                              -- TOTP secret, encrypted at app layer
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TABLE core.user_tenant_roles (
    user_id     UUID NOT NULL REFERENCES core.users(id)   ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES core.tenants(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('owner','admin','operator','viewer','approver')),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by  UUID REFERENCES core.users(id),
    PRIMARY KEY (user_id, tenant_id, role)
);
CREATE INDEX idx_user_tenant_roles_tenant ON core.user_tenant_roles (tenant_id);

CREATE TABLE core.api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES core.tenants(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    prefix       TEXT NOT NULL UNIQUE,                   -- shown in UI: "rfl_live_abc..."
    key_hash     TEXT NOT NULL,                          -- argon2id hash of full key
    scopes       TEXT[] NOT NULL DEFAULT '{}',
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by   UUID REFERENCES core.users(id)
);
CREATE INDEX idx_api_keys_tenant_active ON core.api_keys (tenant_id) WHERE revoked_at IS NULL;

-- HTTP-level idempotency
CREATE TABLE core.idempotency_keys (
    tenant_id        UUID NOT NULL,
    idempotency_key  TEXT NOT NULL,
    request_method   TEXT NOT NULL,
    request_path     TEXT NOT NULL,
    request_hash     TEXT NOT NULL,                     -- sha256(canonical(body))
    response_status  SMALLINT,
    response_headers JSONB,
    response_body    JSONB,
    state            TEXT NOT NULL DEFAULT 'in_flight'
                     CHECK (state IN ('in_flight','completed','failed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '24 hours',
    PRIMARY KEY (tenant_id, idempotency_key)
);
CREATE INDEX idx_idempotency_expiry ON core.idempotency_keys (expires_at);

COMMENT ON TABLE  core.idempotency_keys IS 'HTTP-level idempotency. TTL 24h. Cleaned by janitor job.';
COMMENT ON COLUMN core.idempotency_keys.request_hash IS 'sha256 of canonical JSON body. Used to detect replay-with-different-body conflicts.';


-- =============================================================================
-- audit: event store, snapshots, outbox, subscriptions, chain anchors
-- =============================================================================
-- The heart of the system. Append-only. Never UPDATE, never DELETE.
-- All mutations to aggregates produce events here first.
-- Outbox guarantees at-least-once delivery to the event bus.
-- =============================================================================

CREATE TABLE audit.events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_sequence  BIGSERIAL NOT NULL UNIQUE,         -- monotonic across all streams
    tenant_id        UUID NOT NULL,
    stream_id        TEXT NOT NULL,                     -- e.g. "transaction-<uuid>" or "recovery-<uuid>"
    stream_type      TEXT NOT NULL,                     -- e.g. "transaction", "recovery", "policy"
    version          BIGINT NOT NULL,                   -- monotonic per stream (1, 2, 3, ...)
    event_type       TEXT NOT NULL,                     -- e.g. "PaymentFailed", "DiagnosisGenerated"
    schema_version   SMALLINT NOT NULL DEFAULT 1,       -- for upcasting
    payload          JSONB NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
                                                        -- {causation_id, correlation_id, command_id, actor_id}
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Cryptographic chain
    previous_hash    TEXT,                              -- hex sha256 of previous event in this stream
    event_hash       TEXT NOT NULL,                     -- hex sha256(previous_hash || payload || metadata)

    -- Optimistic concurrency control: uniqueness on (stream, version) prevents conflicting writes
    CONSTRAINT events_stream_version_unique UNIQUE (stream_id, version)
);
CREATE INDEX idx_events_tenant_stream      ON audit.events (tenant_id, stream_id, version);
CREATE INDEX idx_events_tenant_type_time   ON audit.events (tenant_id, stream_type, occurred_at DESC);
CREATE INDEX idx_events_event_type_time    ON audit.events (event_type, occurred_at DESC);
CREATE INDEX idx_events_recorded_at        ON audit.events (recorded_at);
CREATE INDEX idx_events_metadata_command   ON audit.events ((metadata->>'command_id')) WHERE metadata ? 'command_id';
CREATE INDEX idx_events_metadata_correlation ON audit.events ((metadata->>'correlation_id'));

-- Prevent UPDATE/DELETE on events (event store is immutable)
CREATE OR REPLACE FUNCTION audit.events_immutable() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit.events is immutable (no UPDATE or DELETE)';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_events_no_update BEFORE UPDATE ON audit.events
    FOR EACH STATEMENT EXECUTE FUNCTION audit.events_immutable();
CREATE TRIGGER trg_events_no_delete BEFORE DELETE ON audit.events
    FOR EACH STATEMENT EXECUTE FUNCTION audit.events_immutable();

COMMENT ON TABLE  audit.events IS 'Append-only event store. Source of truth.';
COMMENT ON COLUMN audit.events.global_sequence IS 'Monotonic across all streams; used by projections to track progress.';
COMMENT ON COLUMN audit.events.version IS 'Monotonic per stream; used for optimistic concurrency control.';
COMMENT ON COLUMN audit.events.event_hash IS 'sha256(previous_hash || canonical_json(payload) || canonical_json(metadata)).';


-- Snapshots: avoid replaying full stream every load
CREATE TABLE audit.snapshots (
    tenant_id       UUID NOT NULL,
    stream_id       TEXT NOT NULL,
    stream_type     TEXT NOT NULL,
    version         BIGINT NOT NULL,                    -- last event version included
    state           JSONB NOT NULL,
    schema_version  SMALLINT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (stream_id, version)
);
CREATE INDEX idx_snapshots_latest ON audit.snapshots (stream_id, version DESC);


-- Transactional outbox: written in same transaction as events
-- Outbox Relay process polls this and publishes to Redis Streams
CREATE TABLE audit.outbox (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id          UUID NOT NULL REFERENCES audit.events(id),
    tenant_id         UUID NOT NULL,
    destination       TEXT NOT NULL,                    -- "redis-stream:transactions", "redis-stream:recoveries"
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','delivered','failed','dead')),
    attempts          INT NOT NULL DEFAULT 0,
    next_attempt_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at      TIMESTAMPTZ,
    last_error        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_due ON audit.outbox (next_attempt_at) WHERE status = 'pending';
CREATE INDEX idx_outbox_dead ON audit.outbox (created_at DESC) WHERE status = 'dead';


-- Consumer/projection offsets
CREATE TABLE audit.event_subscriptions (
    consumer_name           TEXT PRIMARY KEY,           -- e.g. "trust-view-projection"
    last_processed_sequence BIGINT NOT NULL DEFAULT 0,
    last_processed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','paused','failed')),
    last_error              TEXT
);


-- Cryptographic chain anchors (signed Merkle roots)
CREATE TABLE audit.chain_anchors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,                               -- NULL = global anchor
    start_sequence  BIGINT NOT NULL,
    end_sequence    BIGINT NOT NULL,
    event_count     INT NOT NULL,
    merkle_root     TEXT NOT NULL,                      -- hex sha256
    signature       TEXT NOT NULL,                      -- Ed25519 hex
    signer_key_id   TEXT NOT NULL,                      -- KMS key id or "local-v1"
    signed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_sequence >= start_sequence)
);
CREATE INDEX idx_chain_anchors_tenant_signed ON audit.chain_anchors (tenant_id, signed_at DESC);
CREATE INDEX idx_chain_anchors_range ON audit.chain_anchors (start_sequence, end_sequence);


-- =============================================================================
-- txn: transactions (read model) and attempts
-- =============================================================================

CREATE TABLE txn.transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES core.tenants(id),
    external_id         TEXT NOT NULL,                  -- merchant's transaction id
    customer_ref        TEXT,                           -- merchant's customer id (no PII)

    amount_cents        BIGINT NOT NULL CHECK (amount_cents > 0),
    currency            CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),

    -- Card metadata (NO PAN, NO CVV — PCI scope minimization)
    card_bin            CHAR(6),                        -- first 6 digits of card
    card_last4          CHAR(4),
    card_brand          TEXT,                           -- visa, mastercard, amex, ...
    card_funding        TEXT CHECK (card_funding IN ('credit','debit','prepaid','unknown') OR card_funding IS NULL),
    card_country        CHAR(2),                        -- ISO 3166-1 alpha-2

    issuer_id           TEXT,                           -- resolved from BIN lookup
    gateway_id          TEXT NOT NULL,

    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','succeeded','failed','recovering','recovered','abandoned')),

    initial_failed_at   TIMESTAMPTZ,
    final_resolved_at   TIMESTAMPTZ,

    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, external_id)
);
CREATE INDEX idx_txn_tenant_status_created ON txn.transactions (tenant_id, status, created_at DESC);
CREATE INDEX idx_txn_tenant_issuer_failing ON txn.transactions (tenant_id, issuer_id, status)
    WHERE status IN ('failed','recovering');
CREATE INDEX idx_txn_bin_gateway_failed    ON txn.transactions (card_bin, gateway_id, created_at)
    WHERE status = 'failed';
CREATE INDEX idx_txn_customer              ON txn.transactions (tenant_id, customer_ref) WHERE customer_ref IS NOT NULL;

CREATE TRIGGER trg_txn_updated_at BEFORE UPDATE ON txn.transactions
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

COMMENT ON TABLE txn.transactions IS 'Read model. Derived from events. Never updated outside the transaction aggregate.';


-- Each charge attempt (initial + every retry)
CREATE TABLE txn.attempts (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID NOT NULL,
    transaction_id           UUID NOT NULL REFERENCES txn.transactions(id) ON DELETE CASCADE,
    attempt_number           SMALLINT NOT NULL CHECK (attempt_number >= 1),

    gateway_id               TEXT NOT NULL,
    gateway_request_id       TEXT,                      -- our idempotency key sent to gateway
    gateway_response_id      TEXT,                      -- gateway's identifier for this attempt

    outcome                  TEXT NOT NULL
                             CHECK (outcome IN ('success','soft_decline','hard_decline','error','timeout')),

    decline_code             TEXT,                      -- gateway-specific (e.g. Stripe "insufficient_funds")
    decline_code_normalized  TEXT,                      -- our taxonomy (e.g. "FUNDS_INSUFFICIENT")
    decline_category         TEXT CHECK (decline_category IN
                                ('issuer','network','fraud','authentication','funds','gateway','other')
                                OR decline_category IS NULL),
    decline_message          TEXT,

    -- 3DS / AVS / CVV (no card data, only response codes)
    network_response         JSONB NOT NULL DEFAULT '{}'::jsonb,

    latency_ms               INT,
    attempted_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (transaction_id, attempt_number)
);
CREATE INDEX idx_attempts_tenant_gateway_time ON txn.attempts (tenant_id, gateway_id, attempted_at DESC);
CREATE INDEX idx_attempts_tenant_decline_time ON txn.attempts (tenant_id, decline_code_normalized, attempted_at DESC)
    WHERE outcome IN ('soft_decline','hard_decline');
CREATE INDEX idx_attempts_outcome_time ON txn.attempts (outcome, attempted_at DESC);


-- =============================================================================
-- agent: diagnosis, strategy, risk (read models / projections)
-- =============================================================================

CREATE TABLE agent.diagnoses (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL,
    transaction_id       UUID NOT NULL REFERENCES txn.transactions(id),
    attempt_id           UUID NOT NULL REFERENCES txn.attempts(id),

    root_cause           TEXT NOT NULL,                 -- human summary
    root_cause_category  TEXT NOT NULL
                         CHECK (root_cause_category IN
                            ('issuer_outage','issuer_decline','gateway_degraded','gateway_outage',
                             'network','authentication','fraud_signal','insufficient_funds','other')),
    is_recoverable       BOOLEAN NOT NULL,
    confidence           NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),

    agent_run_id         UUID,                          -- FK to obs.agent_runs (set after)
    prompt_template_id   UUID,
    llm_provider         TEXT,
    llm_model            TEXT,

    reasoning            TEXT,                          -- the agent's narrative
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_diag_tx       ON agent.diagnoses (transaction_id);
CREATE INDEX idx_diag_tenant   ON agent.diagnoses (tenant_id, root_cause_category, created_at DESC);
CREATE INDEX idx_diag_attempt  ON agent.diagnoses (attempt_id);


-- Evidence backing each diagnosis (citations: [1], [2], [3], ...)
CREATE TABLE agent.evidence_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    diagnosis_id    UUID NOT NULL REFERENCES agent.diagnoses(id) ON DELETE CASCADE,
    citation_index  SMALLINT NOT NULL CHECK (citation_index >= 1),

    evidence_type   TEXT NOT NULL CHECK (evidence_type IN
                        ('historical_recovery','gateway_health','issuer_health',
                         'pattern_match','similar_failure','rule_match','external_signal')),

    source_table    TEXT,                               -- which table provided the evidence
    source_query    JSONB,                              -- query that produced it (for replay)

    observation     TEXT NOT NULL,                      -- "Success rate dropped 97%->63% in last 15 min"
    data            JSONB NOT NULL,                     -- the structured measurement
    weight          NUMERIC(3,2),                       -- contribution to confidence

    observed_at     TIMESTAMPTZ NOT NULL,

    UNIQUE (diagnosis_id, citation_index)
);

COMMENT ON TABLE agent.evidence_items IS 'Citations [1], [2], [3] supporting each diagnosis. Replayable via source_query.';


CREATE TABLE agent.strategies (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                       UUID NOT NULL,
    diagnosis_id                    UUID NOT NULL REFERENCES agent.diagnoses(id),

    action_type                     TEXT NOT NULL CHECK (action_type IN
                                        ('immediate_retry','delayed_retry','gateway_reroute',
                                         'rail_switch','payment_link_nudge','graceful_failure',
                                         'manual_review')),
    parameters                      JSONB NOT NULL DEFAULT '{}'::jsonb,
                                    -- e.g. {"delay_minutes": 12, "alt_gateway_id": "adyen"}

    expected_recovery_probability   NUMERIC(3,2) CHECK (expected_recovery_probability BETWEEN 0 AND 1),
    expected_revenue_cents          BIGINT,
    expected_latency_seconds        INT,

    rationale                       TEXT,
    agent_run_id                    UUID,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_strat_diag ON agent.strategies (diagnosis_id);
CREATE INDEX idx_strat_tenant_action ON agent.strategies (tenant_id, action_type, created_at DESC);


CREATE TABLE agent.risk_assessments (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                       UUID NOT NULL,
    strategy_id                     UUID NOT NULL REFERENCES agent.strategies(id),

    financial_risk_score            NUMERIC(3,2) NOT NULL CHECK (financial_risk_score BETWEEN 0 AND 1),
    operational_risk_score          NUMERIC(3,2) NOT NULL CHECK (operational_risk_score BETWEEN 0 AND 1),
    customer_friction_score         NUMERIC(3,2) NOT NULL CHECK (customer_friction_score BETWEEN 0 AND 1),
    duplicate_charge_probability    NUMERIC(5,4) NOT NULL CHECK (duplicate_charge_probability BETWEEN 0 AND 1),

    overall_risk_level              TEXT NOT NULL
                                    CHECK (overall_risk_level IN ('low','medium','high','critical')),

    expected_revenue_impact_cents   BIGINT,
    factors                         JSONB NOT NULL DEFAULT '{}'::jsonb,

    agent_run_id                    UUID,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_risk_strategy ON agent.risk_assessments (strategy_id);
CREATE INDEX idx_risk_level    ON agent.risk_assessments (tenant_id, overall_risk_level, created_at DESC);


-- =============================================================================
-- policy: policies, versions, decisions
-- =============================================================================

CREATE TABLE policy.policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID REFERENCES core.tenants(id),  -- NULL = global default policy
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','active','retired')),
    current_version_id  UUID,                              -- set after first version created
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);
CREATE TRIGGER trg_policies_updated_at BEFORE UPDATE ON policy.policies
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


CREATE TABLE policy.policy_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id       UUID NOT NULL REFERENCES policy.policies(id),
    version         INT  NOT NULL CHECK (version >= 1),
    rules           JSONB NOT NULL,                      -- ordered rule list (Pydantic-validated at app layer)
    rules_hash      TEXT NOT NULL,                       -- sha256 of canonical rules
    notes           TEXT,
    created_by      UUID REFERENCES core.users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at    TIMESTAMPTZ,
    deactivated_at  TIMESTAMPTZ,
    UNIQUE (policy_id, version)
);
CREATE INDEX idx_policy_versions_active ON policy.policy_versions (policy_id)
    WHERE activated_at IS NOT NULL AND deactivated_at IS NULL;

ALTER TABLE policy.policies
    ADD CONSTRAINT fk_policies_current_version
    FOREIGN KEY (current_version_id) REFERENCES policy.policy_versions(id) DEFERRABLE INITIALLY DEFERRED;


-- Every policy evaluation (block, allow, require_approval)
CREATE TABLE policy.decisions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL,
    recovery_id          UUID,                           -- FK below (deferred — recovery table comes later)
    strategy_id          UUID REFERENCES agent.strategies(id),
    policy_version_id    UUID NOT NULL REFERENCES policy.policy_versions(id),

    decision             TEXT NOT NULL CHECK (decision IN ('allow','deny','require_approval')),
    matched_rule_id      TEXT,                           -- which rule fired
    reason               TEXT NOT NULL,
    citations            JSONB,                          -- which evidence backed the decision

    context_snapshot     JSONB NOT NULL,                 -- full input for deterministic replay

    decided_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_decisions_tenant_time   ON policy.decisions (tenant_id, decided_at DESC);
CREATE INDEX idx_decisions_recovery      ON policy.decisions (recovery_id);
CREATE INDEX idx_decisions_strategy      ON policy.decisions (strategy_id);
CREATE INDEX idx_decisions_version_outcome ON policy.decisions (policy_version_id, decision);


-- =============================================================================
-- recovery: sagas, steps, execution attempts, approvals
-- =============================================================================

CREATE TABLE recovery.recoveries (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID NOT NULL REFERENCES core.tenants(id),
    transaction_id           UUID NOT NULL REFERENCES txn.transactions(id),

    state                    TEXT NOT NULL DEFAULT 'created'
                             CHECK (state IN (
                                'created','diagnosed','strategy_proposed','risk_assessed',
                                'policy_evaluated','awaiting_approval','approved',
                                'executing','executed','compensating',
                                'recovered','failed','abandoned')),

    -- Pointers to the produced artifacts at each stage
    diagnosis_id             UUID REFERENCES agent.diagnoses(id),
    strategy_id              UUID REFERENCES agent.strategies(id),
    risk_assessment_id       UUID REFERENCES agent.risk_assessments(id),
    policy_decision_id       UUID REFERENCES policy.decisions(id),
    approval_id              UUID,                       -- FK added below

    -- Idempotency
    recovery_key             TEXT NOT NULL,              -- our deterministic key (per attempt)
    execution_token          TEXT,                       -- token used for gateway calls

    -- Outcome
    outcome                  TEXT CHECK (outcome IN ('recovered','failed','abandoned')),
    recovered_amount_cents   BIGINT,
    recovery_latency_ms      INT,

    -- Saga driver fields
    started_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at             TIMESTAMPTZ,
    next_action_at           TIMESTAMPTZ,                -- when the saga driver should pick this up
    last_error               TEXT,
    retry_count              SMALLINT NOT NULL DEFAULT 0,

    -- Concurrency control for the saga driver
    version                  INT NOT NULL DEFAULT 0,     -- bumped on each state transition

    UNIQUE (tenant_id, recovery_key)
);
CREATE INDEX idx_recoveries_due ON recovery.recoveries (next_action_at)
    WHERE state NOT IN ('recovered','failed','abandoned') AND next_action_at IS NOT NULL;
CREATE INDEX idx_recoveries_tenant_state_time ON recovery.recoveries (tenant_id, state, started_at DESC);
CREATE INDEX idx_recoveries_transaction ON recovery.recoveries (transaction_id);


-- Now the FK that pointed forward from policy.decisions
ALTER TABLE policy.decisions
    ADD CONSTRAINT fk_decisions_recovery
    FOREIGN KEY (recovery_id) REFERENCES recovery.recoveries(id);


-- Saga step history (every state transition)
CREATE TABLE recovery.steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recovery_id     UUID NOT NULL REFERENCES recovery.recoveries(id) ON DELETE CASCADE,
    step_number     INT  NOT NULL CHECK (step_number >= 1),

    from_state      TEXT NOT NULL,
    to_state        TEXT NOT NULL,
    triggered_by    TEXT NOT NULL CHECK (triggered_by IN
                        ('agent','timer','approval','webhook','manual','retry','compensation')),
    handler         TEXT,                                -- which handler executed

    input           JSONB,
    output          JSONB,
    error           JSONB,

    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    duration_ms     INT,

    UNIQUE (recovery_id, step_number)
);
CREATE INDEX idx_steps_recovery_time ON recovery.steps (recovery_id, started_at);


-- Gateway execution attempts — the table that prevents double charges
CREATE TABLE recovery.execution_attempts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    recovery_id         UUID NOT NULL REFERENCES recovery.recoveries(id),
    attempt_number      SMALLINT NOT NULL CHECK (attempt_number >= 1),

    gateway_id          TEXT NOT NULL,
    idempotency_key     TEXT NOT NULL,                   -- sent to gateway as Idempotency-Key

    request_payload     JSONB NOT NULL,
    response_payload    JSONB,

    outcome             TEXT CHECK (outcome IN ('success','failure','timeout','error','unknown')),
    decline_code        TEXT,

    latency_ms          INT,
    cost_cents          INT,                             -- gateway fee on success

    attempted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,

    -- Gateway-side idempotency: same (gateway, key) MUST NOT execute twice
    UNIQUE (gateway_id, idempotency_key),
    UNIQUE (recovery_id, attempt_number)
);
CREATE INDEX idx_exec_recovery ON recovery.execution_attempts (recovery_id, attempt_number);
CREATE INDEX idx_exec_gateway_time ON recovery.execution_attempts (gateway_id, attempted_at DESC);

COMMENT ON TABLE recovery.execution_attempts IS
'Single source of truth for what was actually sent to a gateway. UNIQUE(gateway_id, idempotency_key) is the zero-double-charge guarantee.';


-- HITL approvals
CREATE TABLE recovery.approval_requests (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL,
    recovery_id        UUID NOT NULL REFERENCES recovery.recoveries(id),

    reason             TEXT NOT NULL,                    -- why approval is needed
    proposal           JSONB NOT NULL,                   -- what's being proposed
    evidence_summary   JSONB,
    risk_summary       JSONB,

    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected','expired','cancelled')),

    requested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ NOT NULL,
    resolved_at        TIMESTAMPTZ,
    resolved_by        UUID REFERENCES core.users(id),
    resolution_note    TEXT
);
CREATE INDEX idx_approvals_pending ON recovery.approval_requests (tenant_id, requested_at DESC)
    WHERE status = 'pending';
CREATE INDEX idx_approvals_recovery ON recovery.approval_requests (recovery_id);

ALTER TABLE recovery.recoveries
    ADD CONSTRAINT fk_recoveries_approval
    FOREIGN KEY (approval_id) REFERENCES recovery.approval_requests(id);


-- =============================================================================
-- health: gateway / issuer health time-series + outage detection
-- =============================================================================
-- Bucketed time-series. 1-minute buckets, rolled up by background worker.
-- =============================================================================

CREATE TABLE health.gateway_snapshots (
    gateway_id          TEXT NOT NULL,
    bucket_start        TIMESTAMPTZ NOT NULL,            -- 1-min bucket start

    total_attempts      INT NOT NULL DEFAULT 0,
    successful          INT NOT NULL DEFAULT 0,
    soft_declines       INT NOT NULL DEFAULT 0,
    hard_declines       INT NOT NULL DEFAULT 0,
    errors              INT NOT NULL DEFAULT 0,
    timeouts            INT NOT NULL DEFAULT 0,

    p50_latency_ms      INT,
    p95_latency_ms      INT,
    p99_latency_ms      INT,

    success_rate        NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE WHEN total_attempts > 0
             THEN successful::NUMERIC / total_attempts
             ELSE NULL END
    ) STORED,

    health_score        NUMERIC(3,2),                    -- 0-1; computed by worker

    PRIMARY KEY (gateway_id, bucket_start)
);
CREATE INDEX idx_gw_health_time ON health.gateway_snapshots (bucket_start DESC);
CREATE INDEX idx_gw_health_score_recent ON health.gateway_snapshots (gateway_id, bucket_start DESC)
    WHERE health_score < 0.7;


CREATE TABLE health.issuer_snapshots (
    issuer_id           TEXT NOT NULL,
    bucket_start        TIMESTAMPTZ NOT NULL,

    total_attempts      INT NOT NULL DEFAULT 0,
    successful          INT NOT NULL DEFAULT 0,
    soft_declines       INT NOT NULL DEFAULT 0,
    hard_declines       INT NOT NULL DEFAULT 0,

    success_rate        NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE WHEN total_attempts > 0
             THEN successful::NUMERIC / total_attempts
             ELSE NULL END
    ) STORED,

    health_score        NUMERIC(3,2),

    PRIMARY KEY (issuer_id, bucket_start)
);
CREATE INDEX idx_iss_health_time ON health.issuer_snapshots (bucket_start DESC);


-- Detected outages
CREATE TABLE health.outages (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type       TEXT NOT NULL CHECK (subject_type IN ('gateway','issuer')),
    subject_id         TEXT NOT NULL,                    -- gateway_id or issuer_id
    severity           TEXT NOT NULL CHECK (severity IN ('partial','major','total')),
    started_at         TIMESTAMPTZ NOT NULL,
    ended_at           TIMESTAMPTZ,
    detection_method   TEXT NOT NULL,                    -- 'success_rate_drop','latency_spike','manual'
    confirmed          BOOLEAN NOT NULL DEFAULT false,
    notes              TEXT,
    EXCLUDE USING gist (subject_type WITH =, subject_id WITH =, tstzrange(started_at, COALESCE(ended_at, 'infinity'::timestamptz)) WITH &&)
);
CREATE INDEX idx_outages_subject_time ON health.outages (subject_type, subject_id, started_at DESC);
CREATE INDEX idx_outages_active ON health.outages (subject_type, subject_id) WHERE ended_at IS NULL;


-- =============================================================================
-- intel: memory layers (episodic + pattern + semantic)
-- =============================================================================

-- Episodic memory: structured past outcomes for similarity lookup
CREATE TABLE intel.recovery_episodes (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID,                    -- NULL = cross-tenant aggregate (anonymized)

    -- Signature (the lookup key)
    issuer_id                   TEXT,
    card_bin                    CHAR(6),
    gateway_id                  TEXT,
    decline_code_normalized     TEXT,
    amount_band                 TEXT NOT NULL
                                CHECK (amount_band IN
                                    ('0-10','10-100','100-1k','1k-10k','10k-100k','100k+')),
    time_band                   TEXT NOT NULL
                                CHECK (time_band IN ('business_hours','off_hours','weekend')),

    -- What we tried
    action_type                 TEXT NOT NULL,
    action_parameters           JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- What happened
    outcome                     TEXT NOT NULL CHECK (outcome IN ('recovered','failed','abandoned')),
    recovery_latency_ms         INT,
    recovered_amount_cents      BIGINT,

    -- Provenance
    recovery_id                 UUID REFERENCES recovery.recoveries(id),
    occurred_at                 TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_episodes_lookup ON intel.recovery_episodes
    (issuer_id, gateway_id, decline_code_normalized, amount_band, occurred_at DESC);
CREATE INDEX idx_episodes_tenant_time ON intel.recovery_episodes (tenant_id, occurred_at DESC);
CREATE INDEX idx_episodes_action_outcome ON intel.recovery_episodes (action_type, outcome, occurred_at DESC);


-- Pattern memory: aggregated success rates (materialized view, refreshed every 5 min)
CREATE MATERIALIZED VIEW intel.recovery_patterns AS
SELECT
    issuer_id,
    gateway_id,
    decline_code_normalized,
    amount_band,
    time_band,
    action_type,
    COUNT(*) FILTER (WHERE outcome = 'recovered')              AS recovered_count,
    COUNT(*)                                                   AS total_count,
    COUNT(*) FILTER (WHERE outcome = 'recovered')::NUMERIC
        / NULLIF(COUNT(*), 0)                                  AS success_rate,
    AVG(recovery_latency_ms) FILTER (WHERE outcome = 'recovered') AS avg_recovery_latency_ms,
    SUM(recovered_amount_cents) FILTER (WHERE outcome = 'recovered') AS total_recovered_cents,
    MAX(occurred_at)                                           AS last_seen_at,
    MIN(occurred_at)                                           AS first_seen_at
FROM intel.recovery_episodes
WHERE occurred_at > now() - INTERVAL '90 days'
GROUP BY issuer_id, gateway_id, decline_code_normalized, amount_band, time_band, action_type;

CREATE UNIQUE INDEX uq_recovery_patterns ON intel.recovery_patterns
    (issuer_id, gateway_id, decline_code_normalized, amount_band, time_band, action_type);
CREATE INDEX idx_recovery_patterns_rate ON intel.recovery_patterns (success_rate DESC);

COMMENT ON MATERIALIZED VIEW intel.recovery_patterns IS
'Aggregated pattern memory. Refresh every 5 min via background worker.';


-- Semantic memory: failure embeddings for fuzzy similarity search
CREATE TABLE intel.failure_embeddings (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID,

    source_attempt_id       UUID REFERENCES txn.attempts(id),
    source_diagnosis_id     UUID REFERENCES agent.diagnoses(id),

    failure_description     TEXT NOT NULL,
    embedding               vector(384) NOT NULL,        -- bge-small-en-v1.5 dim
    embedding_model         TEXT NOT NULL DEFAULT 'bge-small-en-v1.5',

    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IVFFlat index for fast cosine search; lists tuned for our scale (~100K rows)
CREATE INDEX idx_failure_embeddings_cos ON intel.failure_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_failure_embeddings_tenant ON intel.failure_embeddings (tenant_id, created_at DESC);


-- =============================================================================
-- obs: agent runs, LLM calls, prompt templates, evaluations
-- =============================================================================

CREATE TABLE obs.prompt_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,                       -- e.g. "diagnosis.system.v3"
    version         INT  NOT NULL CHECK (version >= 1),
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,                       -- sha256
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
CREATE INDEX idx_prompts_active ON obs.prompt_templates (name) WHERE is_active = true;


CREATE TABLE obs.agent_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID,

    agent_name          TEXT NOT NULL,                   -- 'diagnosis','strategy','risk','guard'
    agent_version       TEXT NOT NULL,                   -- semver

    -- Correlation
    recovery_id         UUID REFERENCES recovery.recoveries(id),
    transaction_id      UUID REFERENCES txn.transactions(id),
    parent_run_id       UUID REFERENCES obs.agent_runs(id),
    trace_id            TEXT,                            -- W3C traceparent
    span_id             TEXT,

    status              TEXT NOT NULL DEFAULT 'started'
                        CHECK (status IN ('started','succeeded','failed','timeout','cancelled')),

    input               JSONB NOT NULL,
    output              JSONB,
    error               JSONB,

    -- Aggregated metrics from all LLM calls in this run
    total_cost_usd      NUMERIC(10,6) NOT NULL DEFAULT 0,
    total_tokens_in     INT NOT NULL DEFAULT 0,
    total_tokens_out    INT NOT NULL DEFAULT 0,
    total_calls         INT NOT NULL DEFAULT 0,

    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    latency_ms          INT
);
CREATE INDEX idx_agent_runs_tenant_agent_time ON obs.agent_runs (tenant_id, agent_name, started_at DESC);
CREATE INDEX idx_agent_runs_recovery ON obs.agent_runs (recovery_id);
CREATE INDEX idx_agent_runs_trace ON obs.agent_runs (trace_id);
CREATE INDEX idx_agent_runs_status_time ON obs.agent_runs (status, started_at DESC)
    WHERE status IN ('failed','timeout');


CREATE TABLE obs.llm_calls (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id         UUID REFERENCES obs.agent_runs(id) ON DELETE CASCADE,

    provider             TEXT NOT NULL,                  -- 'groq','gemini','openrouter'
    model                TEXT NOT NULL,
    prompt_template_id   UUID REFERENCES obs.prompt_templates(id),
    prompt_hash          TEXT NOT NULL,                  -- sha256(rendered prompt)

    cache_hit            BOOLEAN NOT NULL DEFAULT false,
    fallback_from        TEXT,                           -- which provider failed before this one

    tokens_in            INT,
    tokens_out           INT,
    cost_usd             NUMERIC(10,6),
    latency_ms           INT,

    validation_status    TEXT CHECK (validation_status IN ('valid','repaired','failed')),
    validation_attempts  SMALLINT NOT NULL DEFAULT 1,

    raw_response         JSONB,                          -- truncated; full goes to Langfuse
    error                JSONB,

    called_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_llm_calls_agent_run ON obs.llm_calls (agent_run_id);
CREATE INDEX idx_llm_calls_provider_time ON obs.llm_calls (provider, called_at DESC);
CREATE INDEX idx_llm_calls_cache_hit ON obs.llm_calls (called_at DESC) WHERE cache_hit = true;
CREATE INDEX idx_llm_calls_prompt_hash ON obs.llm_calls (prompt_hash);


CREATE TABLE obs.agent_evaluations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id    UUID NOT NULL REFERENCES obs.agent_runs(id),

    evaluator       TEXT NOT NULL CHECK (evaluator IN ('llm_judge','golden','human','rule')),
    metric          TEXT NOT NULL,                       -- 'evidence_grounded','citation_valid','schema_valid', ...
    score           NUMERIC(5,4),
    passed          BOOLEAN,
    notes           TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evals_run     ON obs.agent_evaluations (agent_run_id);
CREATE INDEX idx_evals_metric  ON obs.agent_evaluations (metric, evaluated_at DESC);


-- =============================================================================
-- flags: feature flags + kill switches
-- =============================================================================

CREATE TABLE flags.feature_flags (
    key                TEXT PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_.]{1,127}$'),
    description        TEXT,
    flag_type          TEXT NOT NULL CHECK (flag_type IN ('boolean','string','number','json')),
    default_value      JSONB NOT NULL,
    is_killswitch      BOOLEAN NOT NULL DEFAULT false,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_flags_updated_at BEFORE UPDATE ON flags.feature_flags
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


CREATE TABLE flags.tenant_flags (
    tenant_id        UUID NOT NULL REFERENCES core.tenants(id) ON DELETE CASCADE,
    key              TEXT NOT NULL REFERENCES flags.feature_flags(key),
    value            JSONB NOT NULL,
    rollout_percent  SMALLINT CHECK (rollout_percent BETWEEN 0 AND 100),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by       UUID REFERENCES core.users(id),
    PRIMARY KEY (tenant_id, key)
);


CREATE TABLE flags.kill_switches (
    key            TEXT PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_.]{1,127}$'),
                                                        -- e.g. 'recovery.global','gateway.stripe','agent.diagnosis'
    description    TEXT,
    is_active      BOOLEAN NOT NULL DEFAULT false,
    activated_at   TIMESTAMPTZ,
    activated_by   UUID REFERENCES core.users(id),
    reason         TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_killswitch_updated_at BEFORE UPDATE ON flags.kill_switches
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


-- =============================================================================
-- sim: simulation runs + results (for the 100K-transaction benchmark)
-- =============================================================================

CREATE TABLE sim.runs (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                     TEXT NOT NULL,
    seed                     BIGINT NOT NULL,
    config                   JSONB NOT NULL,            -- distributions, gateway mix, issuer mix, etc.

    total_transactions       INT NOT NULL,

    status                   TEXT NOT NULL DEFAULT 'queued'
                             CHECK (status IN ('queued','running','completed','failed','cancelled')),
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by               UUID REFERENCES core.users(id)
);
CREATE INDEX idx_sim_runs_status_time ON sim.runs (status, created_at DESC);


CREATE TABLE sim.results (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                          UUID NOT NULL UNIQUE REFERENCES sim.runs(id) ON DELETE CASCADE,

    -- headline metrics
    total_transactions              INT NOT NULL,
    baseline_succeeded              INT NOT NULL,
    reflow_succeeded                INT NOT NULL,
    recoveries_attempted            INT NOT NULL,
    recoveries_succeeded            INT NOT NULL,

    baseline_success_rate           NUMERIC(5,4) NOT NULL,
    reflow_success_rate             NUMERIC(5,4) NOT NULL,
    success_lift_pp                 NUMERIC(5,4) NOT NULL,   -- percentage points
    recovery_rate                   NUMERIC(5,4) NOT NULL,

    -- trust metrics
    duplicate_charges               INT NOT NULL DEFAULT 0,
    policy_violations               INT NOT NULL DEFAULT 0,

    -- revenue
    total_revenue_baseline_cents    BIGINT NOT NULL,
    total_revenue_reflow_cents      BIGINT NOT NULL,
    total_recovered_revenue_cents   BIGINT NOT NULL,

    -- cost
    total_llm_cost_usd              NUMERIC(10,4) NOT NULL,
    avg_llm_calls_per_recovery      NUMERIC(6,2),

    -- breakdowns
    breakdown_by_decline_code       JSONB,
    breakdown_by_gateway            JSONB,
    breakdown_by_issuer             JSONB,
    breakdown_by_strategy           JSONB,

    completed_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =============================================================================
-- Performance / Partitioning notes (deferred until scale demands it)
-- =============================================================================
-- 1. audit.events    — partition by month on recorded_at when row count > 50M
-- 2. txn.attempts    — partition by month on attempted_at when row count > 50M
-- 3. health.*_snapshots — partition by week on bucket_start when row count > 10M
-- 4. obs.llm_calls    — partition by month on called_at when row count > 50M
-- 5. intel.recovery_episodes — partition by month on occurred_at when row count > 50M
--
-- For v1 demo scale (~100K events), unpartitioned is fine.
-- Partitioning DDL will be in 00x_partitioning.sql when triggered.
-- =============================================================================


-- =============================================================================
-- Row-Level Security (scaffolded; enabled in 002_rls.sql when ready)
-- =============================================================================
-- ALTER TABLE txn.transactions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON txn.transactions
--     USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
-- (repeat for every tenant-scoped table)
-- =============================================================================


-- =============================================================================
-- Seed: minimal data so the app can start
-- =============================================================================

INSERT INTO core.tenants (id, slug, name, tier)
VALUES ('00000000-0000-0000-0000-000000000001', 'demo', 'Demo Merchant', 'standard');

INSERT INTO core.tenant_settings (tenant_id) VALUES ('00000000-0000-0000-0000-000000000001');

INSERT INTO flags.feature_flags (key, description, flag_type, default_value, is_killswitch) VALUES
    ('recovery.enabled',         'Master switch for recovery saga',            'boolean', 'true'::jsonb,  false),
    ('agent.diagnosis.enabled',  'Enable diagnosis agent (LLM)',               'boolean', 'true'::jsonb,  false),
    ('agent.strategy.enabled',   'Enable strategy agent',                      'boolean', 'true'::jsonb,  false),
    ('agent.risk.enabled',       'Enable risk agent',                          'boolean', 'true'::jsonb,  false),
    ('agent.guard.enabled',      'Enable guard agent (final pre-execution check)', 'boolean', 'true'::jsonb, false),
    ('llm.tier2.enabled',        'Allow Tier 2 (full LLM) escalation',         'boolean', 'true'::jsonb,  false),
    ('gateway.stripe.enabled',   'Stripe gateway adapter',                     'boolean', 'true'::jsonb,  false),
    ('gateway.mock.enabled',     'Mock gateway for simulation',                'boolean', 'true'::jsonb,  false);

INSERT INTO flags.kill_switches (key, description, is_active) VALUES
    ('recovery.global',          'Kill all recoveries instantly',              false),
    ('execution.global',         'Kill all gateway executions instantly',      false),
    ('agent.llm.global',         'Disable all LLM calls; fall back to Tier 0/1', false);
