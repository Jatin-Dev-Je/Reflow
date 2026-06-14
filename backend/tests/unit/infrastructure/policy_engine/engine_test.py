"""Policy engine tests.

Two layers of testing:
    * Each built-in rule, in isolation, with crafted contexts.
    * The default policy assembled, exercising ordering and shadowing.

Also covers safety properties:
    * Rules that raise are treated as DENY (fail-safe).
    * First-match-wins ordering.
    * Default outcome when nothing matches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from reflow.core.types import new_tenant_id, new_transaction_id
from reflow.domain.policy import (
    PolicyContext,
    PolicyOutcome,
    RecoveryStrategyKind,
)
from reflow.infrastructure.policy_engine import (
    DEFAULT_POLICY_VERSION_ID,
    Policy,
    PolicyEvaluator,
    Rule,
    build_default_policy,
)
from reflow.infrastructure.policy_engine.policies.duplicate_prevention import (
    duplicate_prevention_rule,
)
from reflow.infrastructure.policy_engine.policies.high_value import high_value_rule
from reflow.infrastructure.policy_engine.policies.retry_limits import retry_limit_rule
from reflow.infrastructure.policy_engine.policies.reroute_safety import reroute_safety_rule

pytestmark = pytest.mark.unit


def _ctx(**overrides) -> PolicyContext:
    base: dict = {
        "tenant_id": new_tenant_id(),
        "transaction_id": new_transaction_id(),
        "amount_cents": 5_000,
        "currency": "USD",
        "issuer_id": "ISSUER_X",
        "gateway_id": "stripe",
        "attempt_number": 2,
        "decline_category": None,
        "decline_code_normalized": None,
        "proposed_strategy": RecoveryStrategyKind.DELAYED_RETRY,
        "proposed_delay_seconds": 60,
        "diagnosis_confidence": 0.9,
        "risk_level": "low",
        "duplicate_charge_probability": 0.01,
        "expected_recovery_probability": 0.7,
        "tenant_max_retries": 3,
        "tenant_high_value_threshold_cents": 5_000_000,
        "tenant_hitl_required_above_cents": 100_000_000,
        "agent_outputs": {},
        "evaluated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return PolicyContext(**base)


def _eval(rule: Rule, ctx: PolicyContext) -> PolicyOutcome:
    policy = Policy(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        version_id=DEFAULT_POLICY_VERSION_ID,
        name="test",
        rules=(rule,),
    )
    return PolicyEvaluator(policy).evaluate(ctx).outcome


# -----------------------------------------------------------------------------
# Individual rules
# -----------------------------------------------------------------------------


class TestRetryLimit:
    def test_allows_attempts_within_budget(self) -> None:
        ctx = _ctx(attempt_number=3, tenant_max_retries=3)
        assert _eval(retry_limit_rule, ctx) == PolicyOutcome.ALLOW  # default-allow

    def test_denies_when_exceeded(self) -> None:
        ctx = _ctx(attempt_number=4, tenant_max_retries=3)
        decision = PolicyEvaluator(
            Policy(
                id=UUID("00000000-0000-0000-0000-000000000098"),
                version_id=DEFAULT_POLICY_VERSION_ID,
                name="t",
                rules=(retry_limit_rule,),
            )
        ).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.DENY
        assert "retry budget" in decision.reason
        assert len(decision.citations) == 1
        assert decision.citations[0].evidence_type.value == "rule_match"


class TestHighValueApproval:
    def test_requires_approval_above_threshold(self) -> None:
        ctx = _ctx(amount_cents=200_000_000, tenant_hitl_required_above_cents=100_000_000)
        decision = PolicyEvaluator(
            Policy(
                id=UUID("00000000-0000-0000-0000-000000000097"),
                version_id=DEFAULT_POLICY_VERSION_ID,
                name="t",
                rules=(high_value_rule,),
            )
        ).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.REQUIRE_APPROVAL
        assert len(decision.citations) == 1

    def test_allows_below_threshold(self) -> None:
        ctx = _ctx(amount_cents=999_999, tenant_hitl_required_above_cents=1_000_000)
        assert _eval(high_value_rule, ctx) == PolicyOutcome.ALLOW


class TestDuplicatePrevention:
    def test_denies_when_probability_high(self) -> None:
        ctx = _ctx(duplicate_charge_probability=0.25)
        decision = PolicyEvaluator(
            Policy(
                id=UUID("00000000-0000-0000-0000-000000000096"),
                version_id=DEFAULT_POLICY_VERSION_ID,
                name="t",
                rules=(duplicate_prevention_rule,),
            )
        ).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.DENY
        assert "duplicate" in decision.reason.lower()

    def test_allows_when_probability_low(self) -> None:
        ctx = _ctx(duplicate_charge_probability=0.001)
        assert _eval(duplicate_prevention_rule, ctx) == PolicyOutcome.ALLOW

    def test_allows_when_no_probability_provided(self) -> None:
        ctx = _ctx(duplicate_charge_probability=None)
        assert _eval(duplicate_prevention_rule, ctx) == PolicyOutcome.ALLOW


class TestRerouteSafety:
    def test_blocks_reroute_below_confidence(self) -> None:
        ctx = _ctx(
            proposed_strategy=RecoveryStrategyKind.GATEWAY_REROUTE,
            diagnosis_confidence=0.5,
        )
        assert _eval(reroute_safety_rule, ctx) == PolicyOutcome.DENY

    def test_allows_reroute_with_high_confidence(self) -> None:
        ctx = _ctx(
            proposed_strategy=RecoveryStrategyKind.GATEWAY_REROUTE,
            diagnosis_confidence=0.95,
        )
        assert _eval(reroute_safety_rule, ctx) == PolicyOutcome.ALLOW

    def test_ignores_non_reroute_strategies(self) -> None:
        ctx = _ctx(
            proposed_strategy=RecoveryStrategyKind.DELAYED_RETRY,
            diagnosis_confidence=0.1,  # very low — but not a reroute, so fine
        )
        assert _eval(reroute_safety_rule, ctx) == PolicyOutcome.ALLOW


# -----------------------------------------------------------------------------
# Full default policy
# -----------------------------------------------------------------------------


class TestDefaultPolicy:
    def test_default_policy_allows_normal_recovery(self) -> None:
        ctx = _ctx()
        decision = PolicyEvaluator(build_default_policy()).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.ALLOW
        assert decision.matched_rule_id is None

    def test_default_policy_denies_when_over_retry_budget(self) -> None:
        ctx = _ctx(attempt_number=10, tenant_max_retries=3)
        decision = PolicyEvaluator(build_default_policy()).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.DENY
        assert decision.matched_rule_id == "retry_limit.exceeded"

    def test_default_policy_requires_approval_for_huge_value(self) -> None:
        ctx = _ctx(
            amount_cents=200_000_000,
            tenant_hitl_required_above_cents=100_000_000,
            duplicate_charge_probability=0.01,
            attempt_number=1,
            tenant_max_retries=3,
        )
        decision = PolicyEvaluator(build_default_policy()).evaluate(ctx)
        assert decision.outcome == PolicyOutcome.REQUIRE_APPROVAL
        assert decision.matched_rule_id == "high_value.requires_approval"

    def test_first_match_wins_ordering(self) -> None:
        """When multiple rules match, the first-listed wins.

        The default policy lists duplicate_prevention before high_value.
        Build a context that would trigger both: very high duplicate-charge
        probability *and* very high value. duplicate_prevention should fire.
        """
        ctx = _ctx(
            duplicate_charge_probability=0.25,           # triggers duplicate_prevention
            amount_cents=200_000_000,                    # triggers high_value
            tenant_hitl_required_above_cents=100_000_000,
        )
        decision = PolicyEvaluator(build_default_policy()).evaluate(ctx)
        assert decision.matched_rule_id == "duplicate_prevention.high_risk"
        assert decision.outcome == PolicyOutcome.DENY


# -----------------------------------------------------------------------------
# Safety: rules that raise
# -----------------------------------------------------------------------------


class TestSafety:
    def test_rule_that_raises_in_when_is_denied(self) -> None:
        def bad_when(_: PolicyContext) -> bool:
            raise RuntimeError("boom")

        def never_called(_: PolicyContext):  # noqa: ARG001
            raise AssertionError("decide should not run when when() raises")

        rule = Rule(id="bad_when", description="", when=bad_when, decide=never_called)
        policy = Policy(
            id=UUID("00000000-0000-0000-0000-000000000050"),
            version_id=DEFAULT_POLICY_VERSION_ID,
            name="t",
            rules=(rule,),
        )
        decision = PolicyEvaluator(policy).evaluate(_ctx())
        assert decision.outcome == PolicyOutcome.DENY
        assert decision.matched_rule_id == "bad_when"

    def test_rule_that_raises_in_decide_is_denied(self) -> None:
        def always(_: PolicyContext) -> bool:
            return True

        def bad_decide(_: PolicyContext):
            raise RuntimeError("boom")

        rule = Rule(id="bad_decide", description="", when=always, decide=bad_decide)
        policy = Policy(
            id=UUID("00000000-0000-0000-0000-000000000051"),
            version_id=DEFAULT_POLICY_VERSION_ID,
            name="t",
            rules=(rule,),
        )
        decision = PolicyEvaluator(policy).evaluate(_ctx())
        assert decision.outcome == PolicyOutcome.DENY
        assert decision.matched_rule_id == "bad_decide"

    def test_no_rules_returns_default_outcome(self) -> None:
        policy = Policy(
            id=UUID("00000000-0000-0000-0000-000000000052"),
            version_id=DEFAULT_POLICY_VERSION_ID,
            name="t",
            rules=(),
            default_outcome=PolicyOutcome.ALLOW,
            default_reason="empty policy",
        )
        decision = PolicyEvaluator(policy).evaluate(_ctx())
        assert decision.outcome == PolicyOutcome.ALLOW
        assert decision.reason == "empty policy"
        assert decision.matched_rule_id is None
