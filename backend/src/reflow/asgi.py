"""ASGI entry point for uvicorn/gunicorn.

    uvicorn reflow.asgi:app
"""

from __future__ import annotations

from reflow.main import create_app

app = create_app()
