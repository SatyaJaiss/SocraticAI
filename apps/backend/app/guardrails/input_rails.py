"""Input rails verifying user requests before routing and LLM execution."""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from app.guardrails.models import RailCheckResult, RailType

logger = logging.getLogger(__name__)


class InputRails:
    """Evaluates incoming student queries for jailbreaks, prompt injection, and abuse."""

    JAILBREAK_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"\bignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?instructions\b", re.IGNORECASE),
        re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous\s+|prior\s+)?rules\b", re.IGNORECASE),
        re.compile(r"\bsystem\s+prompt\s+override\b", re.IGNORECASE),
        re.compile(r"\byou\s+are\s+now\s+(?:DAN|unfiltered|jailbroken|evil)\b", re.IGNORECASE),
        re.compile(r"\bdeveloper\s+mode\s+enabled\b", re.IGNORECASE),
        re.compile(
            r"\breveal\s+(?:your\s+)?(?:system\s+prompt|secret\s+instructions)\b", re.IGNORECASE
        ),
        re.compile(r"\bbypass\s+(?:all\s+)?guardrails\b", re.IGNORECASE),
        re.compile(r"\bexfiltrate\s+(?:data|database|passwords)\b", re.IGNORECASE),
    ]

    def __init__(self, max_length: int = 4000) -> None:
        self.max_length = max_length

    def validate(self, text: str) -> RailCheckResult:
        """Execute deterministic input rail checks."""
        if not text or not text.strip():
            return RailCheckResult(
                allowed=False,
                rail_type=RailType.INPUT,
                reason="Input message cannot be empty.",
                violation_code="EMPTY_INPUT",
            )

        # 1. Length validation
        if len(text) > self.max_length:
            return RailCheckResult(
                allowed=False,
                rail_type=RailType.INPUT,
                reason=f"Input length ({len(text)}) exceeds maximum allowed ({self.max_length}).",
                violation_code="EXCESSIVE_LENGTH",
            )

        # 2. Malformed / Control characters
        if "\x00" in text:
            return RailCheckResult(
                allowed=False,
                rail_type=RailType.INPUT,
                reason="Input contains illegal null byte characters.",
                violation_code="MALFORMED_INPUT",
            )

        # 3. Prompt injection & jailbreak detection
        for pattern in self.JAILBREAK_PATTERNS:
            if pattern.search(text):
                logger.warning("Prompt injection attempt intercepted by InputRails.")
                return RailCheckResult(
                    allowed=False,
                    rail_type=RailType.INPUT,
                    reason="Input contains disallowed jailbreak or prompt override signatures.",
                    violation_code="PROMPT_INJECTION",
                )

        return RailCheckResult(allowed=True, rail_type=RailType.INPUT)
