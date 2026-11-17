"""Controlled PII restoration service for final response presentation."""

from __future__ import annotations

import logging

from app.security.pii.mapping import PIIMappingContext

logger = logging.getLogger(__name__)


class PIIRestorer:
    """Restores permitted PII placeholders in responses delivered back to the student."""

    def __init__(self, escape_html: bool = True) -> None:
        self.escape_html = escape_html

    def restore(
        self,
        text: str,
        context: PIIMappingContext,
        *,
        strict: bool = False,
    ) -> str:
        """Safely restore placeholders using the request-scoped mapping context.

        Args:
            text: Final model response containing placeholders.
            context: The request-scoped mapping context created during input redaction.
            strict: If True, raises ValueError on any unregistered placeholder.
        """
        if not text:
            return ""

        return context.restore_text(text, escape_html=self.escape_html, strict=strict)
