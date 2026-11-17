"""PII domain entities and enums."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PIICategory(StrEnum):
    """Supported categories of personally identifiable information."""

    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    GOVERNMENT_ID = "GOVERNMENT_ID"
    FINANCIAL = "FINANCIAL"
    SENSITIVE_ID = "SENSITIVE_ID"


class PIIEntity(BaseModel):
    """An individual PII span identified within a text."""

    category: PIICategory
    value: str
    start: int
    end: int
    placeholder: str = ""


class PIIAuditSummary(BaseModel):
    """Audit metadata summarizing PII redaction without exposing raw values."""

    request_id: str
    student_id: str
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    total_entities_redacted: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
