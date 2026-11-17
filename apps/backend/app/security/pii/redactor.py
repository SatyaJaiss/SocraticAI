"""PII Redaction pipeline replacing sensitive values with request-scoped placeholders."""

from __future__ import annotations

from app.security.pii.detector import PIIDetector
from app.security.pii.entities import PIIEntity
from app.security.pii.mapping import PIIMappingContext


class PIIRedactor:
    """Sanitizes user input by replacing detected PII entities with scoped placeholders."""

    def __init__(self, detector: PIIDetector | None = None) -> None:
        self.detector = detector or PIIDetector()

    def redact(self, text: str, context: PIIMappingContext) -> tuple[str, list[PIIEntity]]:
        """Redact all PII in text using the provided mapping context.

        Returns:
            Tuple of (redacted_text, list_of_redacted_entities).
        """
        if not text:
            return "", []

        detected_entities = self.detector.detect(text)
        if not detected_entities:
            return text, []

        # Register entities with context to get stable request-scoped placeholders
        registered: list[PIIEntity] = []
        for ent in detected_entities:
            reg_ent = context.register_entity(
                category=ent.category,
                value=ent.value,
                start=ent.start,
                end=ent.end,
            )
            registered.append(reg_ent)

        # Replace from right to left to avoid altering offsets
        result_chars = list(text)
        for ent in reversed(registered):
            result_chars[ent.start : ent.end] = list(ent.placeholder)

        redacted_text = "".join(result_chars)
        return redacted_text, registered
