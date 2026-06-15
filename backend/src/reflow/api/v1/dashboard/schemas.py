"""HTTP schemas for dashboard endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StatusBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: int = 0
    succeeded: int = 0
    failed: int = 0
    recovering: int = 0
    recovered: int = 0
    abandoned: int = 0


class ExecutiveKpis(BaseModel):
    """Top-level KPI cards for the executive dashboard.

    All percentages in [0, 1]; all monetary values in integer cents.
    """

    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    currency: str = Field(default="USD", description="Reporting currency (single-currency v1).")

    total_transactions: int = Field(ge=0)
    total_amount_cents: int = Field(ge=0)

    baseline_succeeded: int = Field(ge=0, description="Succeeded on first attempt.")
    reflow_succeeded: int = Field(
        ge=0, description="baseline_succeeded + recovered — Reflow's effective success."
    )

    baseline_success_rate: float = Field(ge=0, le=1)
    reflow_success_rate: float = Field(ge=0, le=1)
    success_lift_pp: float = Field(
        description="Percentage-point lift Reflow delivered (reflow - baseline).",
    )

    recoveries_attempted: int = Field(ge=0)
    recoveries_succeeded: int = Field(ge=0)
    recovery_rate: float = Field(
        ge=0, le=1, description="recoveries_succeeded / recoveries_attempted, 0 if none."
    )

    revenue_recovered_cents: int = Field(ge=0)

    duplicate_charges: int = Field(
        ge=0, description="Must stay at zero — surfaced loudly if non-zero."
    )
    policy_violations: int = Field(ge=0)

    status_breakdown: StatusBreakdown
