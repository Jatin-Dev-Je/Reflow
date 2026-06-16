"""HTTP schemas for diagnoses + strategies + risk + policy decisions read endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    transaction_id: UUID
    attempt_id: UUID
    root_cause: str
    root_cause_category: str
    is_recoverable: bool
    confidence: float
    agent_run_id: UUID | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    reasoning: str | None = None
    created_at: datetime


class EvidenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    citation_index: int
    evidence_type: str
    source_table: str | None = None
    source_query: dict[str, Any] | None = None
    observation: str
    data: dict[str, Any]
    weight: float | None = None
    observed_at: datetime


class DiagnosisDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnosis: DiagnosisRead
    evidence: list[EvidenceItemRead]


class StrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    diagnosis_id: UUID
    action_type: str
    parameters: dict[str, Any]
    expected_recovery_probability: float | None = None
    expected_revenue_cents: int | None = None
    expected_latency_seconds: int | None = None
    rationale: str | None = None
    agent_run_id: UUID | None = None
    created_at: datetime


class RiskAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    strategy_id: UUID
    financial_risk_score: float
    operational_risk_score: float
    customer_friction_score: float
    duplicate_charge_probability: float
    overall_risk_level: str
    expected_revenue_impact_cents: int | None = None
    factors: dict[str, Any]
    agent_run_id: UUID | None = None
    created_at: datetime


class PolicyDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    recovery_id: UUID | None = None
    strategy_id: UUID | None = None
    policy_version_id: UUID
    decision: str
    matched_rule_id: str | None = None
    reason: str
    citations: dict[str, Any] | list[Any] | None = None
    context_snapshot: dict[str, Any]
    decided_at: datetime
