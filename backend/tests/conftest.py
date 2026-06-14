"""Pytest configuration shared across the suite."""

from __future__ import annotations

import os

# Force test environment before any reflow code is imported.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_NAME", "reflow-backend-test")
