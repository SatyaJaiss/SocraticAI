"""Google Gemini Decisions API provider adapter using official google-genai SDK."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from app.core.config import DecisionModelSettings
from app.decision.base import BaseDecisionProvider
from app.schemas.domain import DecisionResult

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import errors as genai_errors

    _GEMINI_GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None
    genai_errors = None
    _GEMINI_GENAI_AVAILABLE = False


class GeminiDecisionsProvider(BaseDecisionProvider):
    """Decision provider backed by Google's Gemini Decisions API (v1beta)."""

    provider_name = "gemini_decisions"

    def __init__(self, settings: DecisionModelSettings) -> None:
        self.settings = settings
        self.model = settings.gemini_model or "gemini-decision-1"
        self._client: Any = None

        api_key = (
            settings.gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("DECISION_GEMINI_API_KEY")
            or ""
        )
        if _GEMINI_GENAI_AVAILABLE and api_key:
            try:
                self._client = genai.Client(
                    http_options={"api_version": "v1beta"},
                    api_key=api_key,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize Google genai Client: %s", exc)

    @property
    def is_configured(self) -> bool:
        api_key = (
            self.settings.gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("DECISION_GEMINI_API_KEY")
            or ""
        )
        return bool(_GEMINI_GENAI_AVAILABLE and self._client is not None and api_key)

    async def _execute_with_retry(
        self,
        input_text: str,
        questions: dict[str, Any],
    ) -> tuple[Any, float]:
        """Execute decision request with exponential backoff on HTTP 429."""
        attempts = 0
        max_attempts = 3
        backoff = 1.0
        start = time.perf_counter()

        # Format model name (e.g. models/gemini-decision-1 or gemini-decision-1)
        model_name = self.model
        if not model_name.startswith("models/") and "/" not in model_name:
            model_name = f"models/{model_name}"

        while attempts < max_attempts:
            attempts += 1
            try:
                # Bounded timeout on async call
                resp = await asyncio.wait_for(
                    self._client.aio.decisions.create(
                        model=model_name,
                        input=input_text,
                        questions=questions,
                    ),
                    timeout=self.settings.timeout_seconds,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return resp, elapsed_ms

            except TimeoutError:
                logger.warning(
                    "Gemini Decisions API timed out after %.1fs (attempt %d/%d)",
                    self.settings.timeout_seconds,
                    attempts,
                    max_attempts,
                )
                if attempts >= max_attempts:
                    raise

            except Exception as exc:
                err_str = str(exc)
                is_rate_limit = "429" in err_str or "quota" in err_str.lower()
                if is_rate_limit and attempts < max_attempts:
                    logger.warning(
                        "Gemini Decisions API rate limited (429); backing off %.1fs (attempt %d/%d)",
                        backoff,
                        attempts,
                        max_attempts,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.warning(
                        "Gemini Decisions API error on attempt %d/%d: %s",
                        attempts,
                        max_attempts,
                        exc,
                    )
                    if attempts >= max_attempts:
                        raise
        raise RuntimeError("Gemini Decisions call failed after retries")

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
        questions = {
            question_id: {
                "type": "choice",
                "instructions": "Select the single most applicable option.",
                "options": [{"id": k, "description": v} for k, v in options.items()],
            }
        }

        try:
            resp, elapsed_ms = await self._execute_with_retry(context, questions)
            answers = getattr(resp, "answers", {}) or {}
            ans = answers.get(question_id)

            choice_val = getattr(ans, "choice", None) or next(iter(options.keys()))
            confidence = float(getattr(ans, "confidence", 1.0) or 1.0)
            probs = getattr(ans, "probabilities", {}) or {}
            usage = getattr(resp, "usage", {}) or {}

            return DecisionResult(
                decision_value=str(choice_val),
                confidence=confidence,
                probabilities={str(k): float(v) for k, v in probs.items()}
                if isinstance(probs, dict)
                else {},
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
                usage=dict(usage) if isinstance(usage, dict) else {},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.warning("Gemini choose failed: %s", exc)
            return DecisionResult(
                decision_value=next(iter(options.keys())) if options else "error",
                confidence=0.0,
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
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
        questions = {
            question_id: {
                "type": "noul",
                "criteria": criteria,
            }
        }

        try:
            resp, elapsed_ms = await self._execute_with_retry(context, questions)
            answers = getattr(resp, "answers", {}) or {}
            ans = answers.get(question_id)

            noul_val = bool(getattr(ans, "noul", False))
            confidence = float(getattr(ans, "confidence", 1.0 if noul_val else 0.0) or 0.0)
            usage = getattr(resp, "usage", {}) or {}

            return DecisionResult(
                decision_value=noul_val,
                confidence=confidence,
                probabilities={"true": confidence if noul_val else 1.0 - confidence},
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
                usage=dict(usage) if isinstance(usage, dict) else {},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.warning("Gemini evaluate_bool failed: %s", exc)
            return DecisionResult(
                decision_value=False,
                confidence=0.0,
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
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
        if not self.is_configured:
            return DecisionResult(
                decision_value=0.5,
                confidence=0.5,
                provider=self.provider_name,
                model=self.model,
            )

        start = time.perf_counter()
        questions = {
            question_id: {
                "type": "score",
                "instructions": instructions,
                "criteria": rubric,
            }
        }

        try:
            resp, elapsed_ms = await self._execute_with_retry(context, questions)
            answers = getattr(resp, "answers", {}) or {}
            ans = answers.get(question_id)

            raw_score = getattr(ans, "score", 0)
            # Map score to float
            score_num = float(raw_score) if raw_score is not None else 0.0
            max_idx = max(len(rubric) - 1, 1)
            norm_score = round(min(max(score_num / max_idx, 0.0), 1.0), 4)

            confidence = float(getattr(ans, "confidence", 1.0) or 1.0)
            probs = getattr(ans, "probabilities", {}) or {}
            legend = getattr(ans, "legend", None)
            level_name = legend or (
                rubric[int(score_num)] if int(score_num) < len(rubric) else rubric[-1]
            )

            return DecisionResult(
                decision_value=norm_score,
                confidence=confidence,
                probabilities={str(k): float(v) for k, v in probs.items()}
                if isinstance(probs, dict)
                else {},
                rubric_level=str(level_name),
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.warning("Gemini score_rubric failed: %s", exc)
            return DecisionResult(
                decision_value=0.0,
                confidence=0.0,
                provider=self.provider_name,
                model=self.model,
                latency_ms=round(elapsed_ms, 2),
                raw_response={"error": str(exc)},
            )
