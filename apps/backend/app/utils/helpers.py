"""Small, dependency-free helper functions shared across the codebase.

Kept deliberately free of business logic so these can be imported from any
layer without creating import cycles.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    """Timezone-aware current time (UTC)."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string (safe for JSON/DB)."""
    return utc_now().isoformat()


def generate_id(prefix: str) -> str:
    """Return a short, URL-safe, collision-resistant identifier."""
    return f"{prefix}_{secrets.token_hex(8)}"


def safe_json_parse(text: str, *, default: Any = None) -> Any:
    """Best-effort JSON parse."""
    if not text or not text.strip():
        return default
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return default


def sanitize_filename(filename: str) -> str:
    """Strip path separators and control chars from a client-supplied filename."""
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "unnamed"


def ensure_dir(path: str | Path) -> Path:
    """Create a directory (and parents) idempotently; return the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def truncate(text: str, max_chars: int = 500) -> str:
    """Truncate long text with an ellipsis (for logs and previews)."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def parse_score_float(raw: Any, *, default: float = 0.0) -> float:
    """Coerce an LLM-provided score (string/number) to a float safely."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default

