"""Data models and enums for NeMo Guardrails subsystem."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RailType(StrEnum):
    """Categorization of guardrail evaluation boundaries."""

    INPUT = "input"
    RETRIEVAL = "retrieval"
    EXECUTION = "execution"
    OUTPUT = "output"


class RailCheckResult(BaseModel):
    """Result of a guardrail evaluation."""

    allowed: bool
    rail_type: RailType
    reason: str | None = None
    violation_code: str | None = None
    sanitized_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
