"""Dynamic pedagogical strategy and explanation mode selector."""

from __future__ import annotations

from typing import ClassVar

from app.schemas.domain import StrategySelectionResult, StudentProfile
from app.schemas.enums import (
    ExplanationMode,
    MasteryStatus,
    StudentLevel,
    TutoringStrategy,
)


class StrategySelector:
    """Selects optimal tutoring strategy and explanation mode based on student state and query."""

    HINT_KEYWORDS: ClassVar[set[str]] = {
        "hint",
        "clue",
        "help me on this step",
        "i'm stuck",
        "im stuck",
        "stuck",
    }
    GUIDED_KEYWORDS: ClassVar[set[str]] = {
        "guide me",
        "walk me through",
        "solve with me",
        "step by step",
        "let's solve",
        "lets solve",
        "how do i start",
    }
    WORKED_EXAMPLE_KEYWORDS: ClassVar[set[str]] = {
        "example",
        "worked example",
        "show an example",
        "sample problem",
    }
    SOCRATIC_KEYWORDS: ClassVar[set[str]] = {
        "quiz me",
        "ask me questions",
        "socratic",
        "test my reasoning",
        "challenge me",
    }
    ANALOGY_KEYWORDS: ClassVar[set[str]] = {
        "analogy",
        "intuitive",
        "real world",
        "like i'm 5",
        "like im 5",
        "simple terms",
    }
    MATH_KEYWORDS: ClassVar[set[str]] = {
        "mathematical",
        "formula",
        "derivation",
        "proof",
        "rigorous",
        "equation",
    }
    EXAM_KEYWORDS: ClassVar[set[str]] = {
        "exam",
        "test prep",
        "exam oriented",
        "key points",
        "revision",
    }

    def select(
        self,
        message: str,
        student: StudentProfile | None = None,
        concept: str = "",
        mastery_status: MasteryStatus = MasteryStatus.NOT_ATTEMPTED,
        mastery_score: float = 0.0,
        has_active_misconceptions: bool = False,
        prerequisites_missing: list[str] | None = None,
    ) -> StrategySelectionResult:
        """Determine pedagogical strategy and explanation mode."""
        msg_lower = (message or "").strip().lower()
        prereqs = prerequisites_missing or []

        # 1. Determine Strategy
        if any(kw in msg_lower for kw in self.HINT_KEYWORDS):
            strategy = TutoringStrategy.HINT_BASED
            reason = "Student explicitly requested a hint or indicated being stuck."
            confidence = 0.95
        elif any(kw in msg_lower for kw in self.GUIDED_KEYWORDS):
            strategy = TutoringStrategy.GUIDED_PROBLEM_SOLVING
            reason = "Student requested interactive step-by-step guidance."
            confidence = 0.90
        elif any(kw in msg_lower for kw in self.WORKED_EXAMPLE_KEYWORDS):
            strategy = TutoringStrategy.WORKED_EXAMPLE
            reason = "Student requested a concrete worked example."
            confidence = 0.90
        elif any(kw in msg_lower for kw in self.SOCRATIC_KEYWORDS):
            strategy = TutoringStrategy.SOCRATIC_QUESTIONING
            reason = "Student requested guided Socratic dialogue or questioning."
            confidence = 0.90
        elif has_active_misconceptions or mastery_status == MasteryStatus.NEEDS_REVISION:
            strategy = TutoringStrategy.STEP_BY_STEP
            reason = "Active misconceptions or revision needed; adopting structured step-by-step clarification."
            confidence = 0.85
        elif prereqs:
            strategy = TutoringStrategy.STEP_BY_STEP
            reason = f"Unsatisfied prerequisites detected ({', '.join(prereqs[:2])}); structuring foundational explanation."
            confidence = 0.85
        elif mastery_status == MasteryStatus.MASTERED and mastery_score >= 0.85:
            strategy = TutoringStrategy.KNOWLEDGE_CHECK
            reason = "Student demonstrates high mastery; selecting knowledge check or advanced challenge."
            confidence = 0.80
        elif any(kw in msg_lower for kw in self.ANALOGY_KEYWORDS):
            strategy = TutoringStrategy.CONCEPTUAL_ANALOGY
            reason = "Student requested intuitive or analogy-driven understanding."
            confidence = 0.90
        else:
            strategy = TutoringStrategy.DIRECT_EXPLANATION
            reason = "Standard pedagogical explanation tailored to current mastery."
            confidence = 0.75

        # 2. Determine Explanation Mode
        student_level = student.level if student else StudentLevel.INTERMEDIATE

        if any(kw in msg_lower for kw in self.MATH_KEYWORDS):
            mode = ExplanationMode.MATHEMATICAL
        elif any(kw in msg_lower for kw in self.EXAM_KEYWORDS):
            mode = ExplanationMode.EXAM_ORIENTED
        elif any(kw in msg_lower for kw in self.ANALOGY_KEYWORDS):
            mode = ExplanationMode.INTUITIVE
        elif (
            student_level == StudentLevel.BEGINNER or mastery_status == MasteryStatus.NOT_ATTEMPTED
        ):
            mode = ExplanationMode.BEGINNER
        elif student_level == StudentLevel.ADVANCED and mastery_score >= 0.70:
            mode = ExplanationMode.ADVANCED
        else:
            mode = ExplanationMode.INTERMEDIATE

        return StrategySelectionResult(
            strategy=strategy,
            explanation_mode=mode,
            confidence=confidence,
            reasoning=reason,
            target_concept=concept,
            prerequisites_needed=prereqs,
        )
