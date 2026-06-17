"""v1 API router — aggregates all v1 resource routers."""

from __future__ import annotations

from fastapi import APIRouter

from reflow.api.v1.approvals.routes import router as approvals_router
from reflow.api.v1.audit.routes import router as audit_router
from reflow.api.v1.auth.routes import router as auth_router
from reflow.api.v1.dashboard.routes import router as dashboard_router
from reflow.api.v1.diagnosis.routes import router as agents_read_router
from reflow.api.v1.flags.routes import router as flags_router
from reflow.api.v1.policies.routes import router as policies_router
from reflow.api.v1.recoveries.routes import router as recoveries_router
from reflow.api.v1.simulation.routes import router as simulation_router
from reflow.api.v1.system.routes import router as system_router
from reflow.api.v1.transactions.routes import router as transactions_router

router = APIRouter(prefix="/v1")
router.include_router(transactions_router)
router.include_router(audit_router)
router.include_router(recoveries_router)
router.include_router(dashboard_router)
router.include_router(approvals_router)
router.include_router(simulation_router)
router.include_router(agents_read_router)
router.include_router(system_router)
router.include_router(flags_router)
router.include_router(auth_router)
router.include_router(policies_router)
