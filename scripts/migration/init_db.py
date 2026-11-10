"""Database schema initialization and migration helper."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/backend is on path
_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "apps" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import get_settings
from app.db.connection import get_db


def init_database() -> None:
    settings = get_settings()
    db = get_db(settings.database)
    db.create_schema()
    print(f"Database schema initialized at {settings.database.url}")


if __name__ == "__main__":
    init_database()

