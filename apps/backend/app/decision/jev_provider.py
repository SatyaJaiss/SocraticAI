"""TypeSafe AI Jev decision provider adapter."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.core.config import DecisionModelSettings
from app.decision.base import BaseDecisionProvider
from app.schemas.domain import DecisionResult

logger = logging.getLogger(__name__)

try:
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

    _TYPESAFE_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncTypeSafeClient = None
    Choice = None
    Noul = None
    _TYPESAFE_AVAILABLE = False


class JevDecisionProvider(BaseDecisionProvider):
    """Decision provider backed by TypeSafe AI Jev System One."""

    provider_name = "jev"

    def __init__(self, settings: DecisionModelSettings) -> None:
        self.settings = settings
        self.model = settings.jev_model or "jev-latest"
        self._client: Any = None
        api_key = settings.jev_api_key
        if _TYPESAFE_AVAILABLE and api_key:
            try:
                self._client = AsyncTypeSafeClient(api_key=api_key)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize Jev AsyncTypeSafeClient: %s", exc)

    @property
    def is_configured(self) -> bool:
        return bool(_TYPESAFE_AVAILABLE and self._client is not None and self.settings.jev_api_key)

    async def choose(
        self,
        context: str,
        options: dict[str, str],
        *,
        question_id: str = "decision",
    ) -> DecisionResult:
        if not self.is_configured:
            return DecisionResult(
                decision_value=next(iter(options.keys())) if options else "unclear",
                confidence=0.5,
                provider=self.provider_name,
                model=self.model,
            )

        start = time.perf_counter()
        q_dict = {question_id: Choice(criteria=options)}
        ctx = {"context": context}

        try:
            resp = await asyncio.wait_for(
                self._client.system_one(context=ctx, questions=q_dict),
                timeout=self.settings.timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            ans = resp.answers.get(question_id)
            choice = str(getattr(ans, "choice", ""))
            confidence = float(getattr(ans, "confidence", 1.0) or 1.0)
            probabilities = getattr(ans, "probabilities", {}) or {}

            return DecisionResult(
                decision_value=choice,
                confidence=confidence,
                probabilities={str(k): float(v) for k, v in probabilities.items()},
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            logger.warning("Jev choose failed: %s", exc)
            return DecisionResult(
                decision_value=next(iter(options.keys())) if options else "error",
                confidence=0.0,
                provider=self.provider_name,
                model=self.model,
                latency_ms=round((time.perf_counter() - start) * 1000.0, 2),
                raw_response={"error": str(exc)},
            )

    async def evaluate_bool(
        self,
        context: str,
        criteria: str,
        *,
        question_id: str = "boolean_check",
    ) -> DecisionResult:
        if not self.is_configured:
            return DecisionResult(
                decision_value=False,
                confidence=0.5,
                provider=self.provider_name,
                model=self.model,
            )

        start = time.perf_counter()
        crit_dict = (
            criteria
            if isinstance(criteria, dict)
            else {"true": criteria, "false": f"not ({criteria})"}
        )
        q_dict = {question_id: Noul(criteria=crit_dict)}
        ctx = {"context": context}

        try:
            resp = await asyncio.wait_for(
                self._client.system_one(context=ctx, questions=q_dict),
                timeout=self.settings.timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            ans = resp.answers.get(question_id)
            val = bool(getattr(ans, "value", False))
            prob = float(getattr(ans, "probability", 1.0 if val else 0.0) or 0.0)

            return DecisionResult(
                decision_value=val,
                confidence=prob,
                probabilities={"true": prob, "false": 1.0 - prob},
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            logger.warning("Jev evaluate_bool failed: %s", exc)
            return DecisionResult(
                decision_value=False,
                confidence=0.0,
                provider=self.provider_name,
                model=self.model,
                latency_ms=round((time.perf_counter() - start) * 1000.0, 2),
                raw_response={"error": str(exc)},
            )

    async def score_rubric(
        self,
        context: str,
        instructions: str,
        rubric: list[str],
        *,
        question_id: str = "rubric_score",
    ) -> DecisionResult:
        rubric_options = {f"level_{i}": f"Level {i}: {desc}" for i, desc in enumerate(rubric)}
        res = await self.choose(
            f"Instructions: {instructions}\n\nContent:\n{context}",
            rubric_options,
            question_id=question_id,
        )
        # Parse selected level index
        chosen_str = str(res.decision_value)
        level_idx = 0
        if chosen_str.startswith("level_"):
            try:
                level_idx = int(chosen_str.split("_")[1])
            except ValueError:
                level_idx = 0

        # Normalized score between 0.0 and 1.0
        max_idx = max(len(rubric) - 1, 1)
        norm_score = round(level_idx / max_idx, 4)

        return DecisionResult(
            decision_value=norm_score,
            confidence=res.confidence,
            probabilities=res.probabilities,
            rubric_level=rubric[min(level_idx, len(rubric) - 1)] if rubric else None,
            provider=self.provider_name,
            model=self.model,
            latency_ms=res.latency_ms,
        )
