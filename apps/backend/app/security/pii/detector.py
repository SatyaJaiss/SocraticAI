"""Deterministic and heuristic detector for Personally Identifiable Information (PII)."""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from app.security.pii.entities import PIICategory, PIIEntity

logger = logging.getLogger(__name__)


class PIIDetector:
    """Detects sensitive personal data in user inputs using deterministic pattern matchers."""

    # High-precision deterministic regexes
    EMAIL_REGEX: ClassVar[re.Pattern] = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    )

    PHONE_REGEX: ClassVar[re.Pattern] = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b"
    )

    SSN_REGEX: ClassVar[re.Pattern] = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    AADHAAR_REGEX: ClassVar[re.Pattern] = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")
    PAN_REGEX: ClassVar[re.Pattern] = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

    CREDIT_CARD_REGEX: ClassVar[re.Pattern] = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

    IBAN_REGEX: ClassVar[re.Pattern] = re.compile(
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b"
    )

    ADDRESS_REGEX: ClassVar[re.Pattern] = re.compile(
        r"\b\d{1,5}\s+(?:[A-Za-z0-9.-]+\s+){1,4}"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Terrace|Ter)\b"
        r"(?:[,\s]+(?:Apt|Apartment|Suite|Ste|Unit)\s*#?\d+)?"
        r"(?:\s*,\s*[A-Za-z\s]+(?:,\s*[A-Z]{2}\s+\d{5})?)?",
        re.IGNORECASE,
    )

    # Heuristic name patterns: introductions, salutations, signatures, honorifics
    NAME_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(
            r"\b(?:my name is|i am|i'm|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:regards|sincerely|cheers|thanks|best|from|yours truly)[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"),
    ]

    def __init__(self, enabled_categories: set[PIICategory] | None = None) -> None:
        self.enabled_categories = enabled_categories or set(PIICategory)

    def detect(self, text: str) -> list[PIIEntity]:
        """Detect all PII entities within text, returning non-overlapping spans."""
        if not text:
            return []

        candidates: list[PIIEntity] = []

        # 1. Emails
        if PIICategory.EMAIL in self.enabled_categories:
            for match in self.EMAIL_REGEX.finditer(text):
                candidates.append(
                    PIIEntity(
                        category=PIICategory.EMAIL,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # 2. Government IDs
        if PIICategory.GOVERNMENT_ID in self.enabled_categories:
            for regex in (self.SSN_REGEX, self.AADHAAR_REGEX, self.PAN_REGEX):
                for match in regex.finditer(text):
                    candidates.append(
                        PIIEntity(
                            category=PIICategory.GOVERNMENT_ID,
                            value=match.group(0),
                            start=match.start(),
                            end=match.end(),
                        )
                    )

        # 3. Financial
        if PIICategory.FINANCIAL in self.enabled_categories:
            for regex in (self.CREDIT_CARD_REGEX, self.IBAN_REGEX):
                for match in regex.finditer(text):
                    val = match.group(0)
                    # Filter out simple arithmetic strings or short sequences
                    if len(val.replace(" ", "").replace("-", "")) >= 13:
                        candidates.append(
                            PIIEntity(
                                category=PIICategory.FINANCIAL,
                                value=val,
                                start=match.start(),
                                end=match.end(),
                            )
                        )

        # 4. Addresses
        if PIICategory.ADDRESS in self.enabled_categories:
            for match in self.ADDRESS_REGEX.finditer(text):
                candidates.append(
                    PIIEntity(
                        category=PIICategory.ADDRESS,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # 5. Phone numbers
        if PIICategory.PHONE in self.enabled_categories:
            for match in self.PHONE_REGEX.finditer(text):
                val = match.group(0)
                digits = re.sub(r"\D", "", val)
                # Reasonable phone length between 7 and 15 digits
                if 7 <= len(digits) <= 15:
                    candidates.append(
                        PIIEntity(
                            category=PIICategory.PHONE,
                            value=val,
                            start=match.start(),
                            end=match.end(),
                        )
                    )

        # 6. Person Names (Contextual)
        if PIICategory.PERSON in self.enabled_categories:
            for pattern in self.NAME_PATTERNS:
                for match in pattern.finditer(text):
                    name_span = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                    candidates.append(
                        PIIEntity(
                            category=PIICategory.PERSON,
                            value=name_span,
                            start=start,
                            end=end,
                        )
                    )

        return self._resolve_overlaps(candidates)

    def _resolve_overlaps(self, candidates: list[PIIEntity]) -> list[PIIEntity]:
        """Deduplicate overlapping spans prioritizing longer, higher-confidence spans."""
        if not candidates:
            return []

        # Sort primarily by length descending, then by start position
        candidates.sort(key=lambda e: (-(e.end - e.start), e.start))

        chosen: list[PIIEntity] = []
        for entity in candidates:
            # Check if this span overlaps with any already chosen span
            overlaps = any(
                not (entity.end <= existing.start or entity.start >= existing.end)
                for existing in chosen
            )
            if not overlaps:
                chosen.append(entity)

        # Return sorted by original appearance in text
        chosen.sort(key=lambda e: e.start)
        return chosen
