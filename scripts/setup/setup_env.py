"""Environment setup and verification script for local development."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def setup_environment() -> None:
    print(f"Setting up SocraticAI environment at: {_ROOT}")

    # Ensure .env exists
    env_path = _ROOT / ".env"
    env_example = _ROOT / ".env.example"
    if not env_path.exists() and env_example.exists():
        shutil.copy(env_example, env_path)
        print("Copied .env.example to .env")
    else:
        print(".env file already exists")

    # Ensure required data directories exist
    data_dirs = [
        _ROOT / "data" / "uploads",
        _ROOT / "data" / "processed",
        _ROOT / "data" / "sample",
        _ROOT / "logs",
    ]
    for d in data_dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("Data and log directories verified")

    # Run DB schema init
    _backend = _ROOT / "apps" / "backend"
    if str(_backend) not in sys.path:
        sys.path.insert(0, str(_backend))

    try:
        from app.core.config import get_settings
        from app.db.connection import get_db

        settings = get_settings()
        db = get_db(settings.database)
        db.create_schema()
        print("Database schema verified")
    except Exception as exc:
        print(f"Notice: Database check skipped or failed: {exc}")

    print("SocraticAI setup complete.")


if __name__ == "__main__":
    setup_environment()
