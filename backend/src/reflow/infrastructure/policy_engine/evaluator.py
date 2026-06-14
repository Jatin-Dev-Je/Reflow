"""Policy rule engine.

A `Rule` is a typed predicate over `PolicyContext`. A `Policy` is an ordered
tuple of rules — the first one whose `when` matches produces the decision.
If no rule matches, the engine returns the configured default outcome
(typically ALLOW for permissive policies, DENY for restrictive).

Why custom instead of OPA / Cedar? See ADR-0003. Short version: hot path
needs to be in-process, rules are simple, simulation against historical
contexts must be trivial, and we want Pydantic validation of inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from reflow.core.observability.logging import get_logger
from reflow.domain.audit import Citation
from reflow.domain.policy import PolicyContext, PolicyDecision, PolicyOutcome

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Rule:
    """A single ordered rule.

    `when` is a pure predicate against the context — it MUST be deterministic
    and side-effect free; the engine assumes it can be replayed.

    `decide` produces the (outcome, reason, citations) tuple when `when`
    matches.  Citations point back to the data that justified the decision.
    """

    id: str
    description: str
    when: Callable[[PolicyContext], bool]
    decide: Callable[[PolicyContext], tuple[PolicyOutcome, str, list[Citation]]]


@dataclass(frozen=True, slots=True)
class Policy:
    """An ordered collection of rules with a typed default outcome."""

    id: UUID
    version_id: UUID
    name: str
    rules: tuple[Rule, ...] = field(default_factory=tuple)
    default_outcome: PolicyOutcome = PolicyOutcome.ALLOW
    default_reason: str = "No rule matched"


class PolicyEvaluator:
    """Pure, stateless evaluator. Inject the Policy on construction."""

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    def evaluate(self, ctx: PolicyContext) -> PolicyDecision:
        for rule in self._policy.rules:
            try:
                matched = rule.when(ctx)
            except Exception as exc:  # noqa: BLE001 — broad to fail safe
                _logger.error(
                    "policy.rule.when_raised",
                    policy_id=str(self._policy.id),
                    rule_id=rule.id,
                    error=str(exc),
                )
                # A rule that errors is treated as DENY for safety, never silent-allow.
                return PolicyDecision(
                    outcome=PolicyOutcome.DENY,
                    matched_rule_id=rule.id,
                    reason=f"Rule {rule.id!r} raised an error during evaluation",
                    citations=[],
                    policy_version_id=self._policy.version_id,
                    context_snapshot=ctx.model_dump(mode="json"),
                    decided_at=datetime.now(UTC),
                )

            if matched:
                try:
                    outcome, reason, citations = rule.decide(ctx)
                except Exception as exc:  # noqa: BLE001 — fail safe
                    _logger.error(
                        "policy.rule.decide_raised",
                        policy_id=str(self._policy.id),
                        rule_id=rule.id,
                        error=str(exc),
                    )
                    return PolicyDecision(
                        outcome=PolicyOutcome.DENY,
                        matched_rule_id=rule.id,
                        reason=f"Rule {rule.id!r} raised an error producing a decision",
                        citations=[],
                        policy_version_id=self._policy.version_id,
                        context_snapshot=ctx.model_dump(mode="json"),
                        decided_at=datetime.now(UTC),
                    )

                _logger.debug(
                    "policy.decision",
                    policy_id=str(self._policy.id),
                    matched_rule_id=rule.id,
                    outcome=outcome.value,
                )
                return PolicyDecision(
                    outcome=outcome,
                    matched_rule_id=rule.id,
                    reason=reason,
                    citations=citations,
                    policy_version_id=self._policy.version_id,
                    context_snapshot=ctx.model_dump(mode="json"),
                    decided_at=datetime.now(UTC),
                )

        # No rule matched — return the default outcome.
        _logger.debug(
            "policy.decision.default",
            policy_id=str(self._policy.id),
            outcome=self._policy.default_outcome.value,
        )
        return PolicyDecision(
            outcome=self._policy.default_outcome,
            matched_rule_id=None,
            reason=self._policy.default_reason,
            citations=[],
            policy_version_id=self._policy.version_id,
            context_snapshot=ctx.model_dump(mode="json"),
            decided_at=datetime.now(UTC),
        )
