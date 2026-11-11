"""TypeSafe AI Jev System One decision model client adapter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import RoutingSettings
from app.routing.taxonomy import INTENT_CRITERIA, IntentType, RoutingDecision

logger = logging.getLogger(__name__)

try:
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

    _TYPESAFE_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncTypeSafeClient = None
    Choice = None
    Noul = None
    _TYPESAFE_AVAILABLE = False


class JevClient:
    """Async client wrapper for TypeSafe AI Jev decision model."""

    def __init__(self, settings: RoutingSettings) -> None:
        self.settings = settings
        self._client: Any = None
        if _TYPESAFE_AVAILABLE and settings.jev_api_key:
            try:
                self._client = AsyncTypeSafeClient(api_key=settings.jev_api_key)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize AsyncTypeSafeClient: %s", exc)

    @property
    def is_configured(self) -> bool:
        return bool(_TYPESAFE_AVAILABLE and self.settings.jev_enabled and self.settings.jev_api_key)

    async def classify_intent(self, user_message: str) -> RoutingDecision | None:
        """Call Jev System One model with the 10 closed intent taxonomy and privacy safeguards."""
        if not self.is_configured or self._client is None:
            return None

        # Privacy guard: only the text message is forwarded, zero student identifiers or PII
        context = {"message": user_message.strip()}

        questions = {
            "intent": Choice(
                criteria=INTENT_CRITERIA,
            ),
            "is_greeting": Noul(
                criteria="True if the message is primarily a social greeting or conversational opener."
            ),
            "requires_clarification": Noul(
                criteria="True if the user input is too ambiguous or incomplete to proceed without asking clarifying questions."
            ),
        }

        attempts = 0
        max_attempts = max(1, self.settings.jev_retry_count + 1)
        timeout = self.settings.jev_timeout_seconds

        while attempts < max_attempts:
            attempts += 1
            try:
                # Call Jev with timeout
                response = await asyncio.wait_for(
                    self._client.system_one(
                        context=context,
                        questions=questions,
                    ),
                    timeout=timeout,
                )

                intent_ans = response.answers.get("intent")
                if not intent_ans:
                    return None

                raw_choice = str(intent_ans.choice)
                confidence = float(getattr(intent_ans, "confidence", 0.0) or 0.0)
                probabilities = getattr(intent_ans, "probabilities", {}) or {}

                is_greeting = False
                greeting_ans = response.answers.get("is_greeting")
                if greeting_ans:
                    is_greeting = bool(getattr(greeting_ans, "value", False))

                requires_clarification = False
                clarification_ans = response.answers.get("requires_clarification")
                if clarification_ans:
                    requires_clarification = bool(getattr(clarification_ans, "value", False))

                # Validate choice belongs to our taxonomy
                try:
                    chosen_intent = IntentType(raw_choice)
                except ValueError:
                    chosen_intent = IntentType.UNCLEAR

                return RoutingDecision(
                    intent=chosen_intent,
                    confidence=confidence,
                    reasoning=getattr(intent_ans, "reasoning", "") or "",
                    probabilities={k: float(v) for k, v in probabilities.items()},
                    requires_clarification=requires_clarification,
                    is_greeting=is_greeting,
                    source="jev",
                )

            except TimeoutError:
                logger.warning(
                    "Jev classification timed out after %.1fs (attempt %d/%d)",
                    timeout,
                    attempts,
                    max_attempts,
                )
            except Exception as exc:
                logger.warning(
                    "Jev classification failed on attempt %d/%d: %s",
                    attempts,
                    max_attempts,
                    exc,
                )

        return None
