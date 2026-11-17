"""Retrieval rails treating retrieved passages and uploaded documents as untrusted data."""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

from app.guardrails.models import RailCheckResult, RailType

logger = logging.getLogger(__name__)


class RetrievalRails:
    """Sanitizes and evaluates retrieved document passages prior to LLM context inclusion."""

    INDIRECT_INJECTION_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"\b(?:note to ai|instructions for ai|assistant instructions)\b", re.IGNORECASE),
        re.compile(r"\bignore\s+(?:previous|all)\s+instructions\b", re.IGNORECASE),
        re.compile(r"\bsystem\s+override\b", re.IGNORECASE),
        re.compile(r"\bdo\s+not\s+follow\s+the\s+system\s+prompt\b", re.IGNORECASE),
        re.compile(r"\bprint\s+(?:all\s+)?passwords\b", re.IGNORECASE),
        re.compile(r"\boutput\s+the\s+student's\s+api\s+key\b", re.IGNORECASE),
    ]

    def validate_passage(
        self,
        passage_text: str,
        metadata: dict[str, Any] | None = None,
        querying_student_id: str | None = None,
    ) -> RailCheckResult:
        """Evaluate a single retrieved passage for indirect injection and student isolation."""
        meta = metadata or {}

        # 1. Student isolation verification
        doc_student_id = meta.get("student_id")
        if doc_student_id and querying_student_id and doc_student_id != querying_student_id:
            logger.error(
                "Cross-student retrieval isolation violation! Doc student: %s, Querying: %s",
                doc_student_id,
                querying_student_id,
            )
            return RailCheckResult(
                allowed=False,
                rail_type=RailType.RETRIEVAL,
                reason="Passage belongs to another student and violates data isolation.",
                violation_code="STUDENT_ISOLATION_VIOLATION",
                metadata={"document_id": meta.get("document_id")},
            )

        # 2. Indirect prompt injection detection
        for pattern in self.INDIRECT_INJECTION_PATTERNS:
            if pattern.search(passage_text):
                logger.warning("Indirect prompt injection detected in retrieved passage.")
                return RailCheckResult(
                    allowed=False,
                    rail_type=RailType.RETRIEVAL,
                    reason="Retrieved passage contains suspicious prompt injection instructions.",
                    violation_code="INDIRECT_PROMPT_INJECTION",
                    metadata={"document_id": meta.get("document_id")},
                )

        return RailCheckResult(allowed=True, rail_type=RailType.RETRIEVAL)

    def filter_passages(
        self,
        passages: list[dict[str, Any]],
        querying_student_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter a list of retrieved chunks, preserving only safe, authorized passages."""
        safe_passages: list[dict[str, Any]] = []
        for p in passages:
            text = p.get("content") or p.get("text", "")
            meta = p.get("metadata", {})
            res = self.validate_passage(
                text,
                metadata=meta,
                querying_student_id=querying_student_id,
            )
            if res.allowed:
                safe_passages.append(p)
            else:
                logger.warning(
                    "Excluded unsafe retrieved passage (Doc: %s, Reason: %s)",
                    meta.get("document_id"),
                    res.reason,
                )
        return safe_passages
