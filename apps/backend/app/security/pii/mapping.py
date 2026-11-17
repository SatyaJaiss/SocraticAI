"""Request-scoped PII placeholder mapping and isolation context."""

from __future__ import annotations

import html
import re
from typing import ClassVar

from app.security.pii.entities import PIIAuditSummary, PIICategory, PIIEntity


class PIIMappingContext:
    """Request-scoped container mapping PII placeholders to original raw values.

    Guarantees:
    - Never shares placeholders across requests or students.
    - Prevents placeholder collisions by appending deterministic monotonic sequence numbers.
    - Prevents raw values from leaking into logs or external model prompts.
    """

    PLACEHOLDER_REGEX: ClassVar[re.Pattern] = re.compile(
        r"\[(PERSON|EMAIL|PHONE|ADDRESS|GOVERNMENT_ID|FINANCIAL|SENSITIVE_ID)_(\d+)\]"
    )

    def __init__(self, request_id: str, student_id: str) -> None:
        self.request_id = request_id
        self.student_id = student_id
        self._placeholder_to_value: dict[str, str] = {}
        self._value_to_placeholder: dict[str, str] = {}
        self._category_counters: dict[PIICategory, int] = dict.fromkeys(PIICategory, 0)
        self._entities: list[PIIEntity] = []

    def register_entity(self, category: PIICategory, value: str, start: int, end: int) -> PIIEntity:
        """Register a detected PII value and assign or retrieve a request-scoped placeholder."""
        cleaned_value = value.strip()
        if cleaned_value in self._value_to_placeholder:
            placeholder = self._value_to_placeholder[cleaned_value]
        else:
            self._category_counters[category] += 1
            idx = self._category_counters[category]
            placeholder = f"[{category.value}_{idx}]"
            self._value_to_placeholder[cleaned_value] = placeholder
            self._placeholder_to_value[placeholder] = cleaned_value

        entity = PIIEntity(
            category=category,
            value=cleaned_value,
            start=start,
            end=end,
            placeholder=placeholder,
        )
        self._entities.append(entity)
        return entity

    def has_placeholder(self, placeholder: str) -> bool:
        """Check whether the placeholder belongs to this request context."""
        return placeholder in self._placeholder_to_value

    def get_value(self, placeholder: str) -> str | None:
        """Retrieve original value for a placeholder strictly within this request context."""
        return self._placeholder_to_value.get(placeholder)

    def restore_text(
        self,
        text: str,
        *,
        escape_html: bool = True,
        strict: bool = False,
    ) -> str:
        """Replace request-scoped placeholders with their original values safely.

        Args:
            text: Text containing placeholders (e.g. LLM response).
            escape_html: If True, escapes HTML special characters in original values to prevent XSS.
            strict: If True, raises ValueError if an unknown placeholder is encountered.
        """
        if not text or not self._placeholder_to_value:
            return text

        def _replace_match(match: re.Match) -> str:
            placeholder = match.group(0)
            if placeholder in self._placeholder_to_value:
                val = self._placeholder_to_value[placeholder]
                return html.escape(val) if escape_html else val
            if strict:
                raise ValueError(
                    f"Unauthorized placeholder {placeholder!r} not in request mapping context."
                )
            return placeholder

        return self.PLACEHOLDER_REGEX.sub(_replace_match, text)

    def get_audit_summary(self) -> PIIAuditSummary:
        """Return non-sensitive audit metrics detailing PII counts by category."""
        counts = {cat.value: count for cat, count in self._category_counters.items() if count > 0}
        return PIIAuditSummary(
            request_id=self.request_id,
            student_id=self.student_id,
            counts_by_category=counts,
            total_entities_redacted=len(self._entities),
        )

    def clear(self) -> None:
        """Explicitly clear memory mappings."""
        self._placeholder_to_value.clear()
        self._value_to_placeholder.clear()
        self._entities.clear()
