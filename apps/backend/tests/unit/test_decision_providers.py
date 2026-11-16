"""Unit tests for unified decision providers (Jev, Gemini Decisions API, Composite, Relevance Grader)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import DecisionModelSettings
from app.decision.composite import CompositeDecisionProvider
from app.decision.gemini_provider import GeminiDecisionsProvider
from app.decision.jev_provider import JevDecisionProvider
from app.decision.relevance_grader import RetrievalRelevanceGrader
from app.schemas.domain import DecisionResult, RetrievedChunk


class TestJevDecisionProvider:
    @pytest.mark.asyncio
    async def test_jev_choose_success(self):
        settings = DecisionModelSettings(jev_api_key="ts_test_key", primary_provider="jev")
        provider = JevDecisionProvider(settings)

        # Mock AsyncTypeSafeClient
        mock_client = MagicMock()
        mock_answer = MagicMock()
        mock_answer.choice = "tutoring"
        mock_answer.confidence = 0.92
        mock_answer.probabilities = {"tutoring": 0.92, "greeting": 0.08}

        mock_resp = MagicMock()
        mock_resp.answers = {"decision": mock_answer}
        mock_client.system_one = AsyncMock(return_value=mock_resp)

        provider._client = mock_client

        res = await provider.choose(
            "How does backprop work?",
            {"tutoring": "academic question", "greeting": "hello"},
        )
        assert res.decision_value == "tutoring"
        assert res.confidence == 0.92
        assert res.provider == "jev"

    @pytest.mark.asyncio
    async def test_jev_evaluate_bool(self):
        settings = DecisionModelSettings(jev_api_key="ts_test_key")
        provider = JevDecisionProvider(settings)

        mock_client = MagicMock()
        mock_ans = MagicMock()
        mock_ans.value = True
        mock_ans.probability = 0.88
        mock_resp = MagicMock()
        mock_resp.answers = {"bool_q": mock_ans}
        mock_client.system_one = AsyncMock(return_value=mock_resp)
        provider._client = mock_client

        res = await provider.evaluate_bool(
            "Is Paris the capital?", "True if correct", question_id="bool_q"
        )
        assert res.decision_value is True
        assert res.confidence == 0.88


class TestGeminiDecisionsProvider:
    @pytest.mark.asyncio
    async def test_gemini_score_rubric_success(self):
        settings = DecisionModelSettings(
            gemini_api_key="test_gemini_key", gemini_model="gemini-decision-1"
        )
        provider = GeminiDecisionsProvider(settings)

        # Mock google.genai client
        mock_client = MagicMock()
        mock_score_ans = MagicMock()
        mock_score_ans.score = 3
        mock_score_ans.confidence = 0.95
        mock_score_ans.legend = "Highly relevant"

        mock_resp = MagicMock()
        mock_resp.answers = {"relevance": mock_score_ans}
        mock_resp.usage = {"prompt_tokens": 40}

        mock_client.aio.decisions.create = AsyncMock(return_value=mock_resp)
        provider._client = mock_client

        res = await provider.score_rubric(
            context="Passage text here",
            instructions="Score relevance",
            rubric=["Irrelevant", "Partially", "Relevant", "Highly relevant"],
            question_id="relevance",
        )
        assert res.decision_value == 1.0  # Level 3 of 3 is 1.0
        assert res.confidence == 0.95
        assert res.provider == "gemini_decisions"

    @pytest.mark.asyncio
    async def test_gemini_rate_limit_backoff(self):
        settings = DecisionModelSettings(gemini_api_key="test_gemini_key")
        provider = GeminiDecisionsProvider(settings)

        mock_client = MagicMock()
        mock_score_ans = MagicMock()
        mock_score_ans.score = 2
        mock_score_ans.confidence = 0.9
        mock_resp = MagicMock()
        mock_resp.answers = {"relevance": mock_score_ans}

        # First attempt throws 429 quota exhausted, second attempt succeeds
        mock_client.aio.decisions.create = AsyncMock(
            side_effect=[Exception("429 ResourceExhausted: Quota exceeded"), mock_resp]
        )
        provider._client = mock_client

        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            res = await provider.score_rubric(
                context="Passage",
                instructions="Grade",
                rubric=["Low", "Med", "High"],
                question_id="relevance",
            )
            assert res.confidence == 0.9
            mock_sleep.assert_called_once()


class TestCompositeDecisionProvider:
    @pytest.mark.asyncio
    async def test_primary_failover_to_fallback(self):
        settings = DecisionModelSettings(
            primary_provider="jev",
            fallback_provider="gemini_decisions",
            jev_api_key="key",
            gemini_api_key="key",
            confidence_threshold=0.6,
        )
        composite = CompositeDecisionProvider(settings)

        # Mock Jev failure
        composite.jev.choose = AsyncMock(
            return_value=DecisionResult(
                decision_value="err", confidence=0.2, provider="jev", model="jev"
            )
        )
        # Mock Gemini success
        composite.gemini.choose = AsyncMock(
            return_value=DecisionResult(
                decision_value="tutoring",
                confidence=0.9,
                provider="gemini_decisions",
                model="gemini",
            )
        )

        res = await composite.choose("Question", {"tutoring": "desc"})
        assert res.decision_value == "tutoring"
        assert res.provider == "gemini_decisions"


class TestRetrievalRelevanceGrader:
    @pytest.mark.asyncio
    async def test_relevance_grader_scoring_and_gating(self):
        mock_provider = MagicMock()
        # Mock score rubric: first chunk score 0.8, second chunk score 0.1
        mock_provider.score_rubric = AsyncMock(
            side_effect=[
                DecisionResult(decision_value=0.8, confidence=0.9, provider="mock", model="m"),
                DecisionResult(decision_value=0.1, confidence=0.9, provider="mock", model="m"),
            ]
        )
        mock_provider.is_configured = True

        settings = DecisionModelSettings(
            relevance_threshold=0.5,
            relevance_gating_enabled=True,
            candidate_grading_limit=5,
        )
        grader = RetrievalRelevanceGrader(mock_provider, settings)

        c1 = RetrievedChunk(content="Relevant biology notes", source="b.pdf", score=0.7)
        c2 = RetrievedChunk(content="Completely irrelevant recipe", source="r.pdf", score=0.6)

        results = await grader.grade_candidates(
            "Explain photosynthesis", [c1, c2], gate_irrelevant=True
        )
        assert len(results) == 1
        assert results[0].content == "Relevant biology notes"
        assert results[0].relevance_score == 0.8
