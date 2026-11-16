"""Prerequisite-aware recommendation engine utilizing concept dependency graphs."""

from __future__ import annotations

import logging

from app.core.config import AdaptiveRecommendationSettings
from app.repositories.mastery_repository import MasteryRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.domain import (
    Recommendation,
    RecommendationWithPrerequisites,
)
from app.schemas.enums import MasteryStatus

logger = logging.getLogger(__name__)


class PrerequisiteRecommendationEngine:
    """Generates next-step educational recommendations guided by the concept dependency DAG."""

    def __init__(
        self,
        mastery_repo: MasteryRepository,
        student_repo: StudentRepository | None = None,
        settings: AdaptiveRecommendationSettings | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.student_repo = student_repo
        self.settings = settings or AdaptiveRecommendationSettings()

    def generate_recommendations(
        self,
        student_id: str,
        current_topic: str = "",
        limit: int | None = None,
    ) -> list[RecommendationWithPrerequisites]:
        """Rank and return personalized learning activities with prerequisite checks."""
        max_recs = limit or self.settings.max_recommendations
        recommendations: list[RecommendationWithPrerequisites] = []

        # 1. Fetch current mastery profile and weak concepts
        mastery_list = self.mastery_repo.list_mastery(student_id)
        mastery_by_concept = {m.concept.lower(): m for m in mastery_list}

        student = self.student_repo.get(student_id) if self.student_repo else None
        weak_concepts = student.weak_concepts if student else []

        # 2. Check if current topic has unsatisfied prerequisites
        if current_topic:
            sat, missing = self.mastery_repo.check_prerequisites_satisfied(
                student_id=student_id,
                concept=current_topic,
                threshold=self.settings.prerequisite_threshold,
            )
            if not sat:
                for missing_p in missing:
                    recommendations.append(
                        RecommendationWithPrerequisites(
                            concept=missing_p,
                            priority=1,
                            reason=(
                                f"Required foundation for '{current_topic}'. "
                                f"Mastering {missing_p} first will ensure solid comprehension."
                            ),
                            prerequisites_met=True,
                            missing_prerequisites=[],
                            action_type="learn",
                        )
                    )

        # 3. Concepts requiring urgent revision (status NEEDS_REVISION or in weak_concepts)
        for m in mastery_list:
            if m.status == MasteryStatus.NEEDS_REVISION or m.concept in weak_concepts:
                if any(r.concept.lower() == m.concept.lower() for r in recommendations):
                    continue
                # Check prerequisites for this revision topic
                sat, missing = self.mastery_repo.check_prerequisites_satisfied(
                    student_id=student_id,
                    concept=m.concept,
                    threshold=self.settings.prerequisite_threshold,
                )
                recommendations.append(
                    RecommendationWithPrerequisites(
                        concept=m.concept,
                        priority=2,
                        reason=f"Targeted revision needed for '{m.concept}' to reinforce mastery.",
                        prerequisites_met=sat,
                        missing_prerequisites=missing,
                        action_type="review",
                    )
                )

        # 4. In-progress concepts (PARTIALLY_UNDERSTOOD or ATTEMPTED)
        for m in mastery_list:
            if m.status in {MasteryStatus.PARTIALLY_UNDERSTOOD, MasteryStatus.ATTEMPTED}:
                if any(r.concept.lower() == m.concept.lower() for r in recommendations):
                    continue
                sat, missing = self.mastery_repo.check_prerequisites_satisfied(
                    student_id=student_id,
                    concept=m.concept,
                    threshold=self.settings.prerequisite_threshold,
                )
                recommendations.append(
                    RecommendationWithPrerequisites(
                        concept=m.concept,
                        priority=3,
                        reason=f"Continue practice on '{m.concept}' to achieve full mastery.",
                        prerequisites_met=sat,
                        missing_prerequisites=missing,
                        action_type="practice",
                    )
                )

        # 5. Frontier concepts: check known curriculum nodes whose prerequisites are satisfied
        frontier_candidates = [
            "Neural Networks",
            "Backpropagation",
            "CNN",
            "Gradient Descent",
            "Activation Functions",
            "Linear Algebra",
            "Calculus",
        ]
        for candidate in frontier_candidates:
            if candidate.lower() in mastery_by_concept:
                if mastery_by_concept[candidate.lower()].status == MasteryStatus.MASTERED:
                    continue
            if any(r.concept.lower() == candidate.lower() for r in recommendations):
                continue

            sat, missing = self.mastery_repo.check_prerequisites_satisfied(
                student_id=student_id,
                concept=candidate,
                threshold=self.settings.prerequisite_threshold,
            )
            if sat:
                recommendations.append(
                    RecommendationWithPrerequisites(
                        concept=candidate,
                        priority=4,
                        reason=f"Ready to unlock '{candidate}': All foundational prerequisites are satisfied.",
                        prerequisites_met=True,
                        missing_prerequisites=[],
                        action_type="learn",
                    )
                )
            else:
                # Add prerequisite gap recommendation
                recommendations.append(
                    RecommendationWithPrerequisites(
                        concept=candidate,
                        priority=5,
                        reason=f"Prerequisites ({', '.join(missing)}) needed before advancing to '{candidate}'.",
                        prerequisites_met=False,
                        missing_prerequisites=missing,
                        action_type="prerequisite_gap",
                    )
                )

        # Sort recommendations by priority (1 is most urgent)
        recommendations.sort(key=lambda r: r.priority)
        return recommendations[:max_recs]

    def build_legacy_recommendation(
        self,
        student_id: str,
        current_topic: str = "",
    ) -> Recommendation:
        """Convert prerequisite recommendations into legacy Recommendation format."""
        recs = self.generate_recommendations(student_id=student_id, current_topic=current_topic)
        if not recs:
            return Recommendation(
                next_topic="Linear Algebra" if not current_topic else current_topic,
                rationale="Review foundational concepts to strengthen core problem solving.",
                revision_schedule=["Day 1: Foundations", "Day 3: Practice Quiz"],
                daily_plan=["Study concept notes", "Complete 5 practice questions"],
                weak_areas=[],
                suggested_quiz_topics=[current_topic or "Linear Algebra"],
            )

        top = recs[0]
        next_topic = top.concept
        rationale = top.reason

        weak_areas = [r.concept for r in recs if r.action_type in {"review", "prerequisite_gap"}]
        quiz_topics = [r.concept for r in recs if r.prerequisites_met]

        return Recommendation(
            next_topic=next_topic,
            rationale=rationale,
            revision_schedule=[
                f"Session 1: {top.concept}",
                f"Session 2: {recs[1].concept if len(recs) > 1 else 'Review'}",
            ],
            daily_plan=[f"Focus on {top.concept} ({top.action_type})", "Complete assessment"],
            weak_areas=weak_areas[:3],
            suggested_quiz_topics=quiz_topics[:3] or [next_topic],
        )
