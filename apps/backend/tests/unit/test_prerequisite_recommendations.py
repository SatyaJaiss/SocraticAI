"""Unit tests for prerequisite-aware learning recommendations."""

from __future__ import annotations

import pytest
from app.core.config import (
    AdaptiveRecommendationSettings,
    DatabaseSettings,
    MasterySettings,
)
from app.db.connection import Database
from app.repositories.mastery_repository import MasteryRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.enums import PrerequisiteRelation
from app.tutoring.recommendation_engine import PrerequisiteRecommendationEngine


@pytest.fixture
def in_memory_db() -> Database:
    db = Database(DatabaseSettings(url="sqlite:///:memory:"))
    db.create_schema()
    return db


@pytest.fixture
def mastery_repo(in_memory_db: Database) -> MasteryRepository:
    return MasteryRepository(in_memory_db, settings=MasterySettings())


@pytest.fixture
def student_repo(in_memory_db: Database) -> StudentRepository:
    return StudentRepository(in_memory_db)


@pytest.fixture
def rec_engine(
    mastery_repo: MasteryRepository, student_repo: StudentRepository
) -> PrerequisiteRecommendationEngine:
    settings = AdaptiveRecommendationSettings(max_recommendations=5, prerequisite_threshold=0.70)
    return PrerequisiteRecommendationEngine(
        mastery_repo=mastery_repo,
        student_repo=student_repo,
        settings=settings,
    )


def test_missing_prerequisite_prioritized_first(
    mastery_repo: MasteryRepository,
    rec_engine: PrerequisiteRecommendationEngine,
) -> None:
    """When a student wants to learn Neural Networks without Calculus, Calculus is Priority 1."""
    student_id = "student_rec_1"
    mastery_repo.add_prerequisite("Neural Networks", "Linear Algebra", PrerequisiteRelation.DIRECT)
    mastery_repo.add_prerequisite("Neural Networks", "Calculus", PrerequisiteRelation.DIRECT)

    # Student has mastered Linear Algebra only
    for _ in range(3):
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Linear Algebra",
            evidence_score=0.90,
            evidence_confidence=0.90,
        )

    recs = rec_engine.generate_recommendations(
        student_id=student_id, current_topic="Neural Networks"
    )
    assert len(recs) > 0
    # Top recommendation should be Calculus
    assert recs[0].concept == "Calculus"
    assert recs[0].priority == 1
    assert recs[0].action_type == "learn"
    assert "Neural Networks" in recs[0].reason


def test_revision_recommended_for_struggling_concepts(
    mastery_repo: MasteryRepository,
    rec_engine: PrerequisiteRecommendationEngine,
) -> None:
    """Struggling concept is flagged with action_type='review'."""
    student_id = "student_rec_2"

    for _ in range(3):
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Backpropagation",
            evidence_score=0.30,
            evidence_confidence=0.85,
        )

    recs = rec_engine.generate_recommendations(student_id=student_id)
    review_recs = [r for r in recs if r.concept == "Backpropagation"]
    assert len(review_recs) == 1
    assert review_recs[0].action_type == "review"


def test_frontier_concept_unlocked_when_prerequisites_met(
    mastery_repo: MasteryRepository,
    rec_engine: PrerequisiteRecommendationEngine,
) -> None:
    """When Linear Algebra and Calculus are mastered, Neural Networks is unlocked as frontier."""
    student_id = "student_rec_3"
    mastery_repo.seed_default_curriculum()

    for _ in range(3):
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Linear Algebra",
            evidence_score=0.90,
            evidence_confidence=0.90,
        )
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Calculus",
            evidence_score=0.90,
            evidence_confidence=0.90,
        )

    recs = rec_engine.generate_recommendations(student_id=student_id)
    unlocked = [r for r in recs if r.concept == "Neural Networks" and r.prerequisites_met]
    assert len(unlocked) == 1
    assert "All foundational prerequisites are satisfied" in unlocked[0].reason


def test_legacy_recommendation_conversion(
    mastery_repo: MasteryRepository,
    rec_engine: PrerequisiteRecommendationEngine,
) -> None:
    """Legacy Recommendation format is generated successfully."""
    student_id = "student_rec_4"
    mastery_repo.seed_default_curriculum()

    legacy = rec_engine.build_legacy_recommendation(student_id, current_topic="CNN")
    assert legacy.next_topic != ""
    assert legacy.rationale != ""
    assert isinstance(legacy.revision_schedule, list)
    assert isinstance(legacy.daily_plan, list)
