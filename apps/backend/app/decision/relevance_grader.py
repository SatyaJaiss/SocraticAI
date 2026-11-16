"""Retrieval relevance evaluation using structured decision models."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.core.config import DecisionModelSettings
from app.schemas.domain import RetrievedChunk

if TYPE_CHECKING:
    from app.decision.base import BaseDecisionProvider

logger = logging.getLogger(__name__)

RELEVANCE_RUBRIC = [
    "Irrelevant: Does not discuss the topic or question.",
    "Partially relevant: Mentions related terms but does not directly help answer.",
    "Relevant: Provides helpful context, definitions, or partial explanation.",
    "Highly relevant: Directly answers or thoroughly explains the core concept.",
]


class RetrievalRelevanceGrader:
    """Scores candidate document passages for factual relevance using decision models."""

    def __init__(
        self,
        provider: BaseDecisionProvider,
        settings: DecisionModelSettings,
    ) -> None:
        self.provider = provider
        self.settings = settings

    async def grade_passage(self, query: str, chunk: RetrievedChunk) -> float:
        """Grade a single candidate chunk against the question, returning a score in [0.0, 1.0]."""
        context = (
            f"Student Question: {query}\n\n"
            f"Document Source: {chunk.source} (Page {chunk.page or 'N/A'})\n"
            f"Passage Content:\n{chunk.content}"
        )
        res = await self.provider.score_rubric(
            context=context,
            instructions="Evaluate how relevant this course document excerpt is to the student question.",
            rubric=RELEVANCE_RUBRIC,
            question_id="passage_relevance",
        )
        score = float(res.decision_value) if isinstance(res.decision_value, (int, float)) else 0.5
        chunk.relevance_score = round(score, 4)
        return score

    async def grade_candidates(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        gate_irrelevant: bool | None = None,
    ) -> list[RetrievedChunk]:
        """Grade bounded candidates in parallel and optionally filter irrelevant ones."""
        if not candidates or not query.strip() or not self.provider.is_configured:
            return candidates

        limit = min(len(candidates), self.settings.candidate_grading_limit)
        to_grade = candidates[:limit]
        remaining = candidates[limit:]

        # Grade bounded set concurrently
        tasks = [self.grade_passage(query, chunk) for chunk in to_grade]
        scores = await asyncio.gather(*tasks, return_exceptions=True)

        for chunk, score in zip(to_grade, scores, strict=False):
            if isinstance(score, float):
                chunk.relevance_score = score
            else:
                chunk.relevance_score = 0.5

        # Check if gating is enabled
        should_gate = (
            self.settings.relevance_gating_enabled if gate_irrelevant is None else gate_irrelevant
        )
        threshold = self.settings.relevance_threshold

        if should_gate:
            passed = [c for c in to_grade if (c.relevance_score or 0.0) >= threshold]
            logger.debug(
                "Relevance gating filtered %d -> %d candidates (threshold=%.2f)",
                len(to_grade),
                len(passed),
                threshold,
            )
            return passed if passed else to_grade[:1]

        return to_grade + remaining
