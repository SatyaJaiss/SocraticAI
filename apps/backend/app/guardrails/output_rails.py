"""Output rails validating LLM responses before delivery to student."""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from app.guardrails.models import RailCheckResult, RailType

logger = logging.getLogger(__name__)


class OutputRails:
    """Verifies that generated responses do not leak sensitive credentials or harmful content."""

    SENSITIVE_LEAKAGE_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,})\b"),  # OpenAI API key format
        re.compile(r"\b(?:AIzaSy[A-Za-z0-9_-]{33})\b"),  # Google API key format
        re.compile(r"\b(?:ts_live_[A-Za-z0-9_-]{20,})\b"),  # TypeSafe API key format
        re.compile(r"\b(?:postgres(?:ql)?|sqlite):\/\/[^\s]+\b", re.IGNORECASE),  # DB URLs
        re.compile(r"\bBEGIN (?:RSA )?PRIVATE KEY\b"),  # Private keys
        re.compile(r"\bSystem Prompt:\s*You are SocraticAI\b", re.IGNORECASE),  # Raw prompt leakage
    ]

    HARMFUL_CONTENT_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"\bhow to build a bomb\b", re.IGNORECASE),
        re.compile(r"\bhow to hack into\b", re.IGNORECASE),
        re.compile(r"\bcredit card fraud tutorial\b", re.IGNORECASE),
    ]

    def validate(self, text: str) -> RailCheckResult:
        """Evaluate generated text for sensitive leaks, toxic material, or safety violations."""
        if not text:
            return RailCheckResult(allowed=True, rail_type=RailType.OUTPUT)

        # 1. Sensitive credential & secret leakage
        for pattern in self.SENSITIVE_LEAKAGE_PATTERNS:
            if pattern.search(text):
                logger.error("Sensitive information leakage intercepted by OutputRails!")
                return RailCheckResult(
                    allowed=False,
                    rail_type=RailType.OUTPUT,
                    reason="Generated response contained confidential API keys or credentials.",
                    violation_code="SECRET_LEAKAGE",
                )

        # 2. Harmful or dangerous instructions
        for pattern in self.HARMFUL_CONTENT_PATTERNS:
            if pattern.search(text):
                logger.warning("Unsafe content intercepted by OutputRails.")
                return RailCheckResult(
                    allowed=False,
                    rail_type=RailType.OUTPUT,
                    reason="Generated response contained harmful or disallowed advice.",
                    violation_code="HARMFUL_CONTENT",
                )

        return RailCheckResult(allowed=True, rail_type=RailType.OUTPUT)
