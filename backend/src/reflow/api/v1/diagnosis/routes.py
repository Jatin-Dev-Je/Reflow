"""Read endpoints for diagnosis / strategy / risk / policy decisions.

All tenant-scoped, paginated, and bounded by hard page-size caps.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.diagnosis.schemas import (
    DiagnosisDetailRead,
    DiagnosisRead,
    EvidenceItemRead,
    PolicyDecisionRead,
    RiskAssessmentRead,
    StrategyRead,
)
from reflow.infrastructure.persistence.models import (
    DiagnosisModel,
    EvidenceItemModel,
    PolicyDecisionModel,
    RiskAssessmentModel,
    StrategyModel,
)

router = APIRouter(tags=["agents"])

PAGE_DEFAULT = 50
PAGE_MAX = 200


# ----------------------------------------------------------- Diagnoses --------


@router.get(
    "/diagnoses",
    response_model=list[DiagnosisRead],
    summary="List diagnoses",
)
async def list_diagnoses(
    session: SessionDep,
    tenant_id: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[DiagnosisRead]:
    stmt = (
        select(DiagnosisModel)
        .where(DiagnosisModel.tenant_id == tenant_id)
        .order_by(desc(DiagnosisModel.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [DiagnosisRead.model_validate(r) for r in rows]


@router.get(
    "/diagnoses/{diagnosis_id}",
    response_model=DiagnosisDetailRead,
    summary="Get a diagnosis with all citations",
)
async def get_diagnosis(
    diagnosis_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> DiagnosisDetailRead:
    row = await session.get(DiagnosisModel, diagnosis_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found"
        )
    ev_stmt = (
        select(EvidenceItemModel)
        .where(EvidenceItemModel.diagnosis_id == diagnosis_id)
        .order_by(EvidenceItemModel.citation_index)
    )
    evidence = (await session.execute(ev_stmt)).scalars().all()
    return DiagnosisDetailRead(
        diagnosis=DiagnosisRead.model_validate(row),
        evidence=[EvidenceItemRead.model_validate(e) for e in evidence],
    )


# ----------------------------------------------------------- Strategies -------


@router.get(
    "/strategies",
    response_model=list[StrategyRead],
    summary="List strategies",
)
async def list_strategies(
    session: SessionDep,
    tenant_id: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[StrategyRead]:
    stmt = (
        select(StrategyModel)
        .where(StrategyModel.tenant_id == tenant_id)
        .order_by(desc(StrategyModel.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [StrategyRead.model_validate(r) for r in rows]


@router.get(
    "/strategies/{strategy_id}",
    response_model=StrategyRead,
    summary="Get a single strategy",
)
async def get_strategy(
    strategy_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> StrategyRead:
    row = await session.get(StrategyModel, strategy_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found"
        )
    return StrategyRead.model_validate(row)


# ----------------------------------------------------------- Risk -------------


@router.get(
    "/risk-assessments/{risk_id}",
    response_model=RiskAssessmentRead,
    summary="Get a single risk assessment",
)
async def get_risk(
    risk_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> RiskAssessmentRead:
    row = await session.get(RiskAssessmentModel, risk_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Risk assessment not found"
        )
    return RiskAssessmentRead.model_validate(row)


# ----------------------------------------------------------- Policy decisions -


@router.get(
    "/policies/decisions",
    response_model=list[PolicyDecisionRead],
    summary="List policy decisions",
)
async def list_policy_decisions(
    session: SessionDep,
    tenant_id: CurrentTenant,
    decision: Annotated[
        str | None,
        Query(
            description="Filter by outcome: allow | deny | require_approval",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[PolicyDecisionRead]:
    stmt = (
        select(PolicyDecisionModel)
        .where(PolicyDecisionModel.tenant_id == tenant_id)
        .order_by(desc(PolicyDecisionModel.decided_at))
        .limit(limit)
    )
    if decision is not None:
        stmt = stmt.where(PolicyDecisionModel.decision == decision)
    rows = (await session.execute(stmt)).scalars().all()
    return [PolicyDecisionRead.model_validate(r) for r in rows]


@router.get(
    "/policies/decisions/{decision_id}",
    response_model=PolicyDecisionRead,
    summary="Get a single policy decision (full context_snapshot for replay)",
)
async def get_policy_decision(
    decision_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> PolicyDecisionRead:
    row = await session.get(PolicyDecisionModel, decision_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy decision not found"
        )
    return PolicyDecisionRead.model_validate(row)
