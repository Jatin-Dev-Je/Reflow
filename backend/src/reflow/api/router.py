"""Top-level API router — v1 + webhooks."""

from __future__ import annotations

from fastapi import APIRouter

from reflow.api.v1.router import router as v1_router
from reflow.api.webhooks.mock_gateway import router as mock_gateway_router

router = APIRouter()
router.include_router(v1_router)
router.include_router(mock_gateway_router)
