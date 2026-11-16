"""Learning analytics service aggregating progress, mastery, and demonstrated improvement."""

from __future__ import annotations

import logging
from typing import Any

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.mastery_repository import MasteryRepository
from app.repositories.progress_repository import ProgressRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.domain import LearningAnalyticsSummary
from app.schemas.enums import MasteryStatus
from app.tutoring.misconception_detector import MisconceptionDetector

logger = logging.getLogger(__name__)


class LearningAnalyticsService:
    """Aggregates multi-dimensional learning analytics distinguishing activity from true mastery."""

    def __init__(
        self,
        mastery_repo: MasteryRepository,
        quiz_repo: QuizRepository,
        conversation_repo: ConversationRepository,
        progress_repo: ProgressRepository,
        student_repo: StudentRepository | None = None,
        misconception_detector: MisconceptionDetector | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.quiz_repo = quiz_repo
        self.conversation_repo = conversation_repo
        self.progress_repo = progress_repo
        self.student_repo = student_repo
        self.misconception_detector = misconception_detector

    def get_student_summary(self, student_id: str) -> LearningAnalyticsSummary:
        """Compute full learning analytics profile for student."""
        # 1. Activity metrics
        all_messages = self.conversation_repo.list_messages(student_id=student_id, limit=500)
        total_turns = len(all_messages)

        attempts = self.quiz_repo.list_attempts(student_id=student_id, limit=100)
        quizzes_taken = len(attempts)

        # 2. Assessment metrics
        if attempts:
            scores = [a.get("percent", 0.0) for a in attempts]
            avg_score = round(sum(scores) / len(scores), 2)
            high_score = round(max(scores), 2)
        else:
            avg_score = 0.0
            high_score = 0.0

        # Estimate questions attempted (approx 5-8 questions per quiz attempt + evidence count)
        questions_attempted = quizzes_taken * 5

        # 3. Estimated Concept Mastery
        mastery_list = self.mastery_repo.list_mastery(student_id)
        concepts_attempted = len(mastery_list)
        concepts_partially = sum(
            1 for m in mastery_list if m.status == MasteryStatus.PARTIALLY_UNDERSTOOD
        )
        concepts_mastered = sum(1 for m in mastery_list if m.status == MasteryStatus.MASTERED)
        concepts_revision = sum(1 for m in mastery_list if m.status == MasteryStatus.NEEDS_REVISION)

        # 4. Misconceptions tracking
        if self.misconception_detector:
            active_misc = len(self.misconception_detector.get_active_misconceptions(student_id))
            resolved_misc = len(self.misconception_detector.get_resolved_misconceptions(student_id))
        else:
            active_misc = 0
            resolved_misc = 0

        # 5. Demonstrated Learning Improvement
        improvement_score = self._calculate_improvement(student_id, attempts, mastery_list)

        return LearningAnalyticsSummary(
            student_id=student_id,
            total_turns=total_turns,
            quizzes_taken=quizzes_taken,
            questions_attempted=questions_attempted,
            average_quiz_score=avg_score,
            highest_quiz_score=high_score,
            concepts_attempted=concepts_attempted,
            concepts_partially_understood=concepts_partially,
            concepts_mastered=concepts_mastered,
            concepts_needing_revision=concepts_revision,
            concept_mastery_list=mastery_list,
            active_misconceptions_count=active_misc,
            resolved_misconceptions_count=resolved_misc,
            demonstrated_improvement_score=round(improvement_score, 3),
        )

    def _calculate_improvement(
        self,
        student_id: str,
        attempts: list[dict[str, Any]],
        mastery_list: list[Any],
    ) -> float:
        """Calculate demonstrated score and mastery growth over time."""
        if len(attempts) >= 2:
            first_half = attempts[: len(attempts) // 2]
            second_half = attempts[len(attempts) // 2 :]
            first_avg = sum(a.get("percent", 0.0) for a in first_half) / len(first_half)
            second_avg = sum(a.get("percent", 0.0) for a in second_half) / len(second_half)
            delta = (second_avg - first_avg) / 100.0
            return max(0.0, min(1.0, delta + 0.5))  # Normalized 0.0 - 1.0 baseline

        # If few quiz attempts, base on mastery confidence vs initial
        if mastery_list:
            avg_mastery = sum(m.mastery_score for m in mastery_list) / len(mastery_list)
            return round(avg_mastery, 3)

        return 0.0
