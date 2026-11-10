"""SocraticAI — command-line entry point.

Run the API server with::

    python main.py            # reads host/port from settings/.env

The FastAPI app itself lives in :mod:`apps.backend.app.main` and can also be served with
``uvicorn apps.backend.app.main:app --reload``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/backend is on sys.path for direct python main.py invocation
_BACKEND_DIR = Path(__file__).resolve().parent / "apps" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uvicorn

from app.core.config import get_settings
from app.core.logging import setup_logging


def main() -> None:
    """Start the SocraticAI REST API on the configured host/port."""
    settings = get_settings()
    setup_logging(settings.logging)

    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
