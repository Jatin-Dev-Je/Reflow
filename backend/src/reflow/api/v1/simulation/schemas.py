"""HTTP schemas for simulation endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunIngestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1, le=10_000, description="Number of synthetic failures to ingest.")
    seed: int = Field(default=42, description="Deterministic seed.")


class SimulationResultRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    total_transactions: int
    baseline_succeeded: int
    final_succeeded: int
    failures_ingested: int
    recoveries_attempted: int
    recoveries_succeeded: int
    duplicate_charges: int
    baseline_success_rate: float
    final_success_rate: float
    success_lift_pp: float
