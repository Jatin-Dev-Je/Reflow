"""Default policy bundle — the rules every tenant gets out of the box.

Ordering matters: kill-switch / deny-on-violation rules MUST run before
ALLOW-style rules. Within a tier, more specific rules go first so they
shadow general ones.

Tenants get this bundle assigned as version 1 when their account is
provisioned. They can override or extend it by creating new policy_versions
via the API.
"""

from __future__ import annotations

from uuid import UUID

from reflow.domain.policy import PolicyOutcome
from reflow.infrastructure.policy_engine.evaluator import Policy
from reflow.infrastructure.policy_engine.policies.duplicate_prevention import (
    duplicate_prevention_rule,
)
from reflow.infrastructure.policy_engine.policies.high_value import high_value_rule
from reflow.infrastructure.policy_engine.policies.retry_limits import retry_limit_rule
from reflow.infrastructure.policy_engine.policies.reroute_safety import reroute_safety_rule

# Stable IDs for the default policy / version so tests and seed data can
# reference them deterministically.
DEFAULT_POLICY_ID = UUID("00000000-0000-0000-0000-000000000010")
DEFAULT_POLICY_VERSION_ID = UUID("00000000-0000-0000-0000-000000000011")


def build_default_policy() -> Policy:
    return Policy(
        id=DEFAULT_POLICY_ID,
        version_id=DEFAULT_POLICY_VERSION_ID,
        name="default-recovery-policy",
        rules=(
            # Hard denies first — these are zero-double-charge + retry-budget guards.
            duplicate_prevention_rule,
            retry_limit_rule,
            # Routing safety.
            reroute_safety_rule,
            # HITL escalation — runs after the deny guards so we don't ask humans
            # to approve something that's already going to be denied.
            high_value_rule,
        ),
        default_outcome=PolicyOutcome.ALLOW,
        default_reason="No restrictive rule matched — recovery permitted.",
    )
