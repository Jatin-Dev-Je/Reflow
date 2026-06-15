"""v1 API router — aggregates all v1 resource routers."""

from __future__ import annotations

from fastapi import APIRouter

from reflow.api.v1.audit.routes import router as audit_router
from reflow.api.v1.dashboard.routes import router as dashboard_router
from reflow.api.v1.recoveries.routes import router as recoveries_router
from reflow.api.v1.transactions.routes import router as transactions_router

router = APIRouter(prefix="/v1")
router.include_router(transactions_router)
router.include_router(audit_router)
router.include_router(recoveries_router)
router.include_router(dashboard_router)
