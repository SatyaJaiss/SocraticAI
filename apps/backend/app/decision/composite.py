"""Composite decision provider with automated fallback and shadow evaluation mode."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import DecisionModelSettings
from app.decision.base import BaseDecisionProvider
from app.decision.gemini_provider import GeminiDecisionsProvider
from app.decision.jev_provider import JevDecisionProvider
from app.schemas.domain import DecisionResult

logger = logging.getLogger(__name__)


class DisabledDecisionProvider(BaseDecisionProvider):
    """Fallback dummy provider when decision models are disabled."""

    provider_name = "disabled"

    @property
    def is_configured(self) -> bool:
        return True

    async def choose(
        self,
        context: str,
        options: dict[str, str],
        *,
        question_id: str = "decision",
    ) -> DecisionResult:
        default_val = next(iter(options.keys())) if options else "unclear"
        return DecisionResult(
            decision_value=default_val,
            confidence=0.5,
            provider=self.provider_name,
            model="none",
        )

    async def evaluate_bool(
        self,
        context: str,
        criteria: str,
        *,
        question_id: str = "boolean_check",
    ) -> DecisionResult:
        return DecisionResult(
            decision_value=True,
            confidence=0.5,
            provider=self.provider_name,
            model="none",
        )

    async def score_rubric(
        self,
        context: str,
        instructions: str,
        rubric: list[str],
        *,
        question_id: str = "rubric_score",
    ) -> DecisionResult:
        return DecisionResult(
            decision_value=0.5,
            confidence=0.5,
            rubric_level=rubric[len(rubric) // 2] if rubric else "moderate",
            provider=self.provider_name,
            model="none",
        )


class CompositeDecisionProvider(BaseDecisionProvider):
    """Unified coordinator managing primary provider, failover fallback, and shadow benchmarking."""

    def __init__(self, settings: DecisionModelSettings) -> None:
        self.settings = settings
        self.provider_name = "composite"

        # Instantiate providers
        self.jev = JevDecisionProvider(settings)
        self.gemini = GeminiDecisionsProvider(settings)
        self.disabled = DisabledDecisionProvider()

        self._providers: dict[str, BaseDecisionProvider] = {
            "jev": self.jev,
            "gemini_decisions": self.gemini,
            "disabled": self.disabled,
        }
        self._tasks: set[asyncio.Task] = set()

    @property
    def is_configured(self) -> bool:
        primary = self._get_primary()
        return primary.is_configured

    def _get_primary(self) -> BaseDecisionProvider:
        mode = (self.settings.primary_provider or "jev").lower()
        return self._providers.get(mode, self.disabled)

    def _get_fallback(self) -> BaseDecisionProvider:
        mode = (self.settings.fallback_provider or "disabled").lower()
        return self._providers.get(mode, self.disabled)

    def _get_shadow_secondary(self) -> BaseDecisionProvider | None:
        if not self.settings.shadow_mode:
            return None
        primary_name = (self.settings.primary_provider or "jev").lower()
        if primary_name == "jev" and self.gemini.is_configured:
            return self.gemini
        if primary_name == "gemini_decisions" and self.jev.is_configured:
            return self.jev
        return None

    async def _run_with_fallback(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> DecisionResult:
        primary = self._get_primary()
        shadow = self._get_shadow_secondary()

        # If shadow mode is active, schedule secondary call concurrently
        shadow_task: asyncio.Task | None = None
        if shadow:
            shadow_method = getattr(shadow, method_name)
            shadow_task = asyncio.create_task(shadow_method(*args, **kwargs))

        # Execute primary
        try:
            if primary.is_configured:
                method = getattr(primary, method_name)
                res = await method(*args, **kwargs)
                if res.confidence >= self.settings.confidence_threshold:
                    if shadow_task:
                        bg_task = asyncio.create_task(self._log_shadow_comparison(res, shadow_task))
                        self._tasks.add(bg_task)
                        bg_task.add_done_callback(self._tasks.discard)
                    return res
                logger.debug(
                    "Primary provider %s confidence %.2f below threshold %.2f",
                    primary.provider_name,
                    res.confidence,
                    self.settings.confidence_threshold,
                )
        except Exception as exc:
            logger.warning(
                "Primary decision provider %s failed: %s; invoking fallback",
                primary.provider_name,
                exc,
            )

        # Fallback
        fallback = self._get_fallback()
        if fallback != primary and fallback.is_configured:
            fallback_method = getattr(fallback, method_name)
            return await fallback_method(*args, **kwargs)

        # Return default from disabled provider
        disabled_method = getattr(self.disabled, method_name)
        return await disabled_method(*args, **kwargs)

    async def _log_shadow_comparison(
        self, primary_res: DecisionResult, shadow_task: asyncio.Task
    ) -> None:
        """Background logger comparing primary vs shadow decision."""
        try:
            shadow_res = await shadow_task
            agreement = primary_res.decision_value == shadow_res.decision_value
            logger.info(
                "[SHADOW EVAL] Primary: %s (%s, lat=%.1fms, val=%s) vs Shadow: %s (%s, lat=%.1fms, val=%s) -> Agreement: %s",
                primary_res.provider,
                primary_res.model,
                primary_res.latency_ms,
                primary_res.decision_value,
                shadow_res.provider,
                shadow_res.model,
                shadow_res.latency_ms,
                shadow_res.decision_value,
                agreement,
            )
        except Exception as exc:
            logger.debug("Shadow evaluation task failed: %s", exc)

    async def choose(
        self,
        context: str,
        options: dict[str, str],
        *,
        question_id: str = "decision",
    ) -> DecisionResult:
        return await self._run_with_fallback("choose", context, options, question_id=question_id)

    async def evaluate_bool(
        self,
        context: str,
        criteria: str,
        *,
        question_id: str = "boolean_check",
    ) -> DecisionResult:
        return await self._run_with_fallback(
            "evaluate_bool", context, criteria, question_id=question_id
        )

    async def score_rubric(
        self,
        context: str,
        instructions: str,
        rubric: list[str],
        *,
        question_id: str = "rubric_score",
    ) -> DecisionResult:
        return await self._run_with_fallback(
            "score_rubric", context, instructions, rubric, question_id=question_id
        )
