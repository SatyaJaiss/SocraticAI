"""Unified PII protection and safe restoration service."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.security.pii.detector import PIIDetector
from app.security.pii.entities import PIIAuditSummary, PIICategory, PIIEntity
from app.security.pii.mapping import PIIMappingContext
from app.security.pii.redactor import PIIRedactor
from app.security.pii.restorer import PIIRestorer

if TYPE_CHECKING:
    from app.core.config import PIISettings

logger = logging.getLogger(__name__)


class PIIProtectionService:
    """Production service enforcing PII redaction before ANY external model/API call

    and safe placeholder restoration for final student-facing responses.
    """

    def __init__(self, settings: PIISettings | None = None) -> None:
        self.settings = settings
        categories = None
        if settings and settings.enabled_categories:
            categories = {
                PIICategory(cat.upper())
                for cat in settings.enabled_categories
                if cat.upper() in PIICategory.__members__
            }
        self.detector = PIIDetector(enabled_categories=categories)
        self.redactor = PIIRedactor(self.detector)
        self.restorer = PIIRestorer(escape_html=settings.escape_html if settings else True)

    def create_context(self, student_id: str, request_id: str | None = None) -> PIIMappingContext:
        """Create a new, isolated request-scoped mapping context."""
        req_id = request_id or str(uuid.uuid4())
        return PIIMappingContext(request_id=req_id, student_id=student_id)

    def redact_user_input(
        self,
        text: str,
        student_id: str,
        request_id: str | None = None,
        context: PIIMappingContext | None = None,
    ) -> tuple[str, PIIMappingContext, list[PIIEntity]]:
        """Sanitize student input prior to routing, guardrails, retrieval, or inference.

        Returns:
            Tuple of (redacted_text, mapping_context, list_of_redacted_entities).
        """
        if context is None:
            context = self.create_context(student_id=student_id, request_id=request_id)

        redacted_text, entities = self.redactor.redact(text, context)

        # Telemetry/metric hook (imported lazily to avoid circular imports)
        try:
            from app.telemetry.metrics import record_pii_redaction

            for ent in entities:
                record_pii_redaction(ent.category.value)
        except Exception:
            pass

        return redacted_text, context, entities

    def restore_response(
        self,
        text: str,
        context: PIIMappingContext,
        *,
        strict: bool = False,
    ) -> str:
        """Restore request-scoped placeholders back to original values in user response."""
        return self.restorer.restore(text, context, strict=strict)

    def get_audit_summary(self, context: PIIMappingContext) -> PIIAuditSummary:
        """Return non-sensitive audit metrics for security compliance."""
        return context.get_audit_summary()
