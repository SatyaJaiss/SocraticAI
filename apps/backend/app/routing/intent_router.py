"""Hybrid intent router combining TypeSafe AI Jev model with deterministic fallback."""

from __future__ import annotations

import logging
import re

from app.core.config import RoutingSettings
from app.routing.jev_client import JevClient
from app.routing.taxonomy import IntentType, RoutingDecision

logger = logging.getLogger(__name__)


class JevIntentRouter:
    """Intelligent intent classifier combining Jev System One model with fast deterministic fallback."""

    def __init__(
        self,
        settings: RoutingSettings,
        jev_client: JevClient | None = None,
    ) -> None:
        self.settings = settings
        self.jev_client = jev_client or JevClient(settings)

    async def route(self, user_message: str) -> RoutingDecision:
        """Route the user message to one of the 10 canonical intents."""
        # 1. Pre-validation
        text = user_message.strip()
        if not text:
            return RoutingDecision(
                intent=IntentType.UNCLEAR,
                confidence=1.0,
                reasoning="Input message is empty or whitespace only.",
                requires_clarification=True,
                source="prevalidation",
            )

        # Gibberish or purely punctuation/symbols
        cleaned = re.sub(r"[^\w\s]", "", text)
        if len(text) <= 2 and not cleaned.isalnum():
            return RoutingDecision(
                intent=IntentType.UNCLEAR,
                confidence=0.95,
                reasoning="Input consists purely of punctuation symbols.",
                requires_clarification=True,
                source="prevalidation",
            )

        # 2. Try Jev System One model if enabled
        if self.jev_client.is_configured:
            decision = await self.jev_client.classify_intent(text)
            if decision is not None:
                # Confidence evaluation
                if decision.confidence >= self.settings.confidence_high_threshold:
                    return decision
                elif decision.confidence < self.settings.confidence_low_threshold:
                    logger.debug(
                        "Jev confidence %.2f below low threshold %.2f; checking deterministic rules",
                        decision.confidence,
                        self.settings.confidence_low_threshold,
                    )
                    fallback_decision = self._deterministic_classify(text)
                    if fallback_decision.confidence > decision.confidence:
                        return fallback_decision
                    # If still low, flag clarification
                    decision.requires_clarification = True
                    return decision
                else:
                    # Medium confidence
                    return decision

        # 3. Deterministic rule-based fallback
        return self._deterministic_classify(text)

    def _deterministic_classify(self, text: str) -> RoutingDecision:
        """Deterministic keyword and regex classification."""
        lower = text.lower().strip()

        # --- Unclear (Explicit gibberish / symbols) ---
        if lower in {"...", "???", "asdfghjk", "ummm wait", "it depends", "?"}:
            return RoutingDecision(
                intent=IntentType.UNCLEAR,
                confidence=0.90,
                reasoning="Deterministic match: ambiguous or incomplete input.",
                requires_clarification=True,
                source="deterministic_fallback",
            )

        # --- Document Question (Must check before generic questions) ---
        doc_patterns = [
            r"\b(in\s+my\s+notes?|in\s+the\s+(uploaded\s+)?(pdf|document|slides?|notes?|file))\b",
            r"\b(according\s+to\s+(the|my)\s+(uploaded\s+)?(notes?|pdf|slides?|document|text|file|syllabus))\b",
            r"\b(from\s+the\s+uploaded\s+(file|pdf|notes?|slides?|document))\b",
            r"\b(what\s+does\s+(the|my)\s+(document|pdf|text|syllabus|notes?)\s+say)\b",
            r"\b(slide\s+\d+|lecture\s+notes?)\b",
        ]
        if any(re.search(pat, lower) for pat in doc_patterns):
            return RoutingDecision(
                intent=IntentType.DOCUMENT_QUESTION,
                confidence=0.90,
                reasoning="Deterministic match: explicit document or notes reference.",
                source="deterministic_fallback",
            )

        # --- Assessment Submission ---
        assessment_patterns = [
            r"\b(here\s+are\s+my\s+answers?|submit\s+(my\s+)?(quiz\s+)?answers?)\b",
            r"\b(grade\s+my\s+(answers?|quiz|test|solution|work))\b",
            r"\b(evaluate\s+my\s+(answers?|work|submission|essay))\b",
            r"\b(check\s+my\s+work)\b",
            r"\b\d+\s*[a-d]\s*,\s*\d+\s*[a-d]\b",
        ]
        if any(re.search(pat, lower) for pat in assessment_patterns):
            return RoutingDecision(
                intent=IntentType.ASSESSMENT,
                confidence=0.90,
                reasoning="Deterministic match: answer submission or grading request.",
                source="deterministic_fallback",
            )

        # --- Quiz / Practice ---
        quiz_patterns = [
            r"\b(quiz\s+me|give\s+me\s+a\s+quiz|practice\s+quiz|test\s+me)\b",
            r"\b(practice\s+(some\s+)?(questions?|problem\s+drills?))\b",
            r"\b(problem\s+drill|test\s+my\s+knowledge)\b",
            r"\b(generate\s+(\d+\s+)?practice\s+questions?)\b",
            r"\b(generate\s+(a\s+)?quiz|start\s+(a\s+)?(practice\s+)?quiz)\b",
        ]
        if any(re.search(pat, lower) for pat in quiz_patterns):
            return RoutingDecision(
                intent=IntentType.QUIZ,
                confidence=0.90,
                reasoning="Deterministic match: request for quiz or practice drill.",
                source="deterministic_fallback",
            )

        # --- Memory Query ---
        memory_patterns = [
            r"\b(what\s+did\s+we\s+discuss|what\s+did\s+we\s+talk\s+about)\b",
            r"\b(do\s+you\s+remember|remember\s+my|what\s+were\s+my)\b",
            r"\b(what\s+was\s+the\s+last\s+(thing|lesson|topic))\b",
            r"\b(recall\s+our\s+(past\s+)?(session|conversation))\b",
            r"\b(my\s+weak\s+(concepts|topics|areas)|weak\s+areas)\b",
        ]
        if any(re.search(pat, lower) for pat in memory_patterns):
            return RoutingDecision(
                intent=IntentType.MEMORY_QUERY,
                confidence=0.88,
                reasoning="Deterministic match: inquiry into past sessions or memory.",
                source="deterministic_fallback",
            )

        # --- Learning Progress ---
        progress_patterns = [
            r"\b(how\s+am\s+i\s+doing|my\s+progress|learning\s+progress)\b",
            r"\b(show\s+my\s+(scores?|mastery|progress))\b",
            r"\b(learning\s+curve|my\s+analytics|overall\s+performance|performance\s+analytics)\b",
            r"\b(how\s+many\s+topics\s+(have\s+i|did\s+i)\s+master)\b",
            r"\b(quiz\s+stats|performance\s+stats)\b",
        ]
        if any(re.search(pat, lower) for pat in progress_patterns):
            return RoutingDecision(
                intent=IntentType.LEARNING_PROGRESS,
                confidence=0.88,
                reasoning="Deterministic match: learning progress or analytics query.",
                source="deterministic_fallback",
            )

        # --- Greeting ---
        greeting_patterns = [
            r"^(hello|hi|hey|howdy|greetings|sup)\b",
            r"\b(good\s+(morning|afternoon|evening))\b",
            r"\b(hello|hi|hey)\s+(there|tutor|socraticai)\b",
        ]
        if lower in {"hello", "hi", "hey", "greetings", "howdy", "sup"} or any(
            re.search(pat, lower) for pat in greeting_patterns
        ):
            if not any(
                v in lower
                for v in ["explain", "teach", "calculus", "photosynthesis", "quiz", "derive"]
            ):
                return RoutingDecision(
                    intent=IntentType.GREETING,
                    confidence=0.95,
                    reasoning="Deterministic match: greeting keywords.",
                    is_greeting=True,
                    source="deterministic_fallback",
                )

        # --- Small talk ---
        small_talk_patterns = [
            r"\b(thank\s*you|thanks|thx|cheers)\b",
            r"\b(how\s+are\s+you|how\'s\s+it\s+going|what\'s\s+up)\b",
            r"\b(who\s+(are|created|made)\s+you)\b",
            r"\b(you(\'re|\s+are)\s+(great|awesome|helpful|smart|cool))\b",
            r"\b(goodbye|bye|see\s+you|farewell|good\s+night|have\s+a\s+wonderful\s+day)\b",
        ]
        if any(re.search(pat, lower) for pat in small_talk_patterns):
            return RoutingDecision(
                intent=IntentType.SMALL_TALK,
                confidence=0.90,
                reasoning="Deterministic match: small talk conversational pattern.",
                source="deterministic_fallback",
            )

        # --- Off Topic ---
        off_topic_patterns = [
            r"\b(weather\s+in|recipe\s+for|stock\s+price|bitcoin\s+price)\b",
            r"\b(who\s+won\s+the\s+(game|match|super\s*bowl|world\s*cup|football))\b",
            r"\b(movie\s+(to\s+watch|recommendations?)|best\s+restaurant)\b",
        ]
        if any(re.search(pat, lower) for pat in off_topic_patterns):
            return RoutingDecision(
                intent=IntentType.OFF_TOPIC,
                confidence=0.85,
                reasoning="Deterministic match: off-topic general query.",
                source="deterministic_fallback",
            )

        # --- Tutoring (Default academic inquiry) ---
        tutoring_indicators = [
            r"\b(teach\s+me|explain|what\s+is|how\s+does|why\s+does|can\s+you\s+help\s+me\s+understand)\b",
            r"\b(walk\s+me\s+through|solve|derive|calculate|proof|concept\s+of)\b",
            r"\b(difference\s+between|fundamental\s+theorem|photosynthesis|calculus|mitosis|meiosis|resistance|quadratic|binary\s+search)\b",
        ]
        if any(re.search(pat, lower) for pat in tutoring_indicators):
            return RoutingDecision(
                intent=IntentType.TUTORING,
                confidence=0.88,
                reasoning="Deterministic match: pedagogical tutoring inquiry.",
                source="deterministic_fallback",
            )

        # Fallback to TUTORING if multi-word statement
        if len(lower.split()) >= 3:
            return RoutingDecision(
                intent=IntentType.TUTORING,
                confidence=0.70,
                reasoning="Deterministic fallback: multi-word educational statement.",
                source="deterministic_fallback",
            )

        # Fallback to UNCLEAR if very short and unrecognized
        return RoutingDecision(
            intent=IntentType.UNCLEAR,
            confidence=0.50,
            reasoning="Deterministic fallback: unrecognized short text.",
            requires_clarification=True,
            source="deterministic_fallback",
        )
