"""Unit tests for JevIntentRouter and Jev decision model integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.core.config import RoutingSettings
from app.routing.intent_router import JevIntentRouter
from app.routing.taxonomy import IntentType, RoutingDecision


class TestJevIntentRouter:
    @pytest.fixture
    def router(self) -> JevIntentRouter:
        settings = RoutingSettings(
            jev_enabled=False,  # default offline/deterministic
            confidence_high_threshold=0.70,
            confidence_low_threshold=0.40,
        )
        return JevIntentRouter(settings)

    @pytest.mark.asyncio
    async def test_prevalidation_empty_and_whitespace(self, router):
        decision = await router.route("   \n\t  ")
        assert decision.intent == IntentType.UNCLEAR
        assert decision.requires_clarification is True
        assert decision.source == "prevalidation"

    @pytest.mark.asyncio
    async def test_prevalidation_symbols_only(self, router):
        decision = await router.route("???")
        assert decision.intent == IntentType.UNCLEAR
        assert decision.requires_clarification is True

    @pytest.mark.asyncio
    async def test_deterministic_greeting(self, router):
        decision = await router.route("Hello there!")
        assert decision.intent == IntentType.GREETING
        assert decision.is_greeting is True
        assert decision.confidence >= 0.90

    @pytest.mark.asyncio
    async def test_deterministic_small_talk(self, router):
        decision = await router.route("Thank you so much for the help!")
        assert decision.intent == IntentType.SMALL_TALK
        assert decision.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_deterministic_quiz(self, router):
        decision = await router.route("Give me a practice quiz on linear algebra")
        assert decision.intent == IntentType.QUIZ
        assert decision.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_deterministic_assessment(self, router):
        decision = await router.route("Here are my answers: 1A, 2C, 3B")
        assert decision.intent == IntentType.ASSESSMENT
        assert decision.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_deterministic_document_question(self, router):
        decision = await router.route("According to the uploaded notes, what is entropy?")
        assert decision.intent == IntentType.DOCUMENT_QUESTION
        assert decision.confidence >= 0.80

    @pytest.mark.asyncio
    async def test_deterministic_memory_query(self, router):
        decision = await router.route("What did we discuss in our last session?")
        assert decision.intent == IntentType.MEMORY_QUERY
        assert decision.confidence >= 0.80

    @pytest.mark.asyncio
    async def test_deterministic_progress(self, router):
        decision = await router.route("Show my learning progress and mastery level")
        assert decision.intent == IntentType.LEARNING_PROGRESS
        assert decision.confidence >= 0.80

    @pytest.mark.asyncio
    async def test_deterministic_off_topic(self, router):
        decision = await router.route("What is the recipe for chocolate cake?")
        assert decision.intent == IntentType.OFF_TOPIC
        assert decision.confidence >= 0.80

    @pytest.mark.asyncio
    async def test_deterministic_tutoring(self, router):
        decision = await router.route("Explain how photosynthesis converts sunlight into glucose")
        assert decision.intent == IntentType.TUTORING
        assert decision.confidence >= 0.80

    @pytest.mark.asyncio
    async def test_mocked_jev_client_high_confidence(self):
        settings = RoutingSettings(jev_enabled=True, jev_api_key="test-key")
        mock_client = AsyncMock()
        mock_client.is_configured = True
        mock_client.classify_intent.return_value = RoutingDecision(
            intent=IntentType.TUTORING,
            confidence=0.96,
            reasoning="Student is asking for an in-depth lesson on cellular respiration.",
            source="jev",
        )

        router = JevIntentRouter(settings, jev_client=mock_client)
        decision = await router.route("Explain cellular respiration")

        assert decision.intent == IntentType.TUTORING
        assert decision.confidence == 0.96
        assert decision.source == "jev"

    @pytest.mark.asyncio
    async def test_mocked_jev_client_low_confidence_fallback(self):
        settings = RoutingSettings(
            jev_enabled=True,
            jev_api_key="test-key",
            confidence_high_threshold=0.70,
            confidence_low_threshold=0.40,
        )
        mock_client = AsyncMock()
        mock_client.is_configured = True
        mock_client.classify_intent.return_value = RoutingDecision(
            intent=IntentType.UNCLEAR,
            confidence=0.30,
            reasoning="Ambiguous",
            source="jev",
        )

        router = JevIntentRouter(settings, jev_client=mock_client)
        decision = await router.route("Hello tutor!")

        # Low confidence Jev should fall back to deterministic which classifies "Hello tutor!" as GREETING with high confidence
        assert decision.intent == IntentType.GREETING
        assert decision.source == "deterministic_fallback"

    @pytest.mark.asyncio
    async def test_mocked_jev_client_failure_fallback(self):
        settings = RoutingSettings(jev_enabled=True, jev_api_key="test-key")
        mock_client = AsyncMock()
        mock_client.is_configured = True
        mock_client.classify_intent.return_value = None  # Simulates network failure or timeout

        router = JevIntentRouter(settings, jev_client=mock_client)
        decision = await router.route("Give me a quiz on calculus")

        assert decision.intent == IntentType.QUIZ
        assert decision.source == "deterministic_fallback"
