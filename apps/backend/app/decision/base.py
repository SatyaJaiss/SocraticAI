"""Unified Decision Provider abstractions and normalized contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import DecisionResult


class BaseDecisionProvider(ABC):
    """Abstract contract for structured decision models (Jev and Gemini Decisions)."""

    provider_name: str

    @abstractmethod
    async def choose(
        self,
        context: str,
        options: dict[str, str],
        *,
        question_id: str = "decision",
    ) -> DecisionResult:
        """Categorical decision: select one option from a dictionary of {label: description}."""

    @abstractmethod
    async def evaluate_bool(
        self,
        context: str,
        criteria: str,
        *,
        question_id: str = "boolean_check",
    ) -> DecisionResult:
        """Binary decision (noul): returns True/False with confidence probability."""

    @abstractmethod
    async def score_rubric(
        self,
        context: str,
        instructions: str,
        rubric: list[str],
        *,
        question_id: str = "rubric_score",
    ) -> DecisionResult:
        """Ordered rubric score: evaluates context against ordered levels."""

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if API credentials and required dependencies are ready."""
