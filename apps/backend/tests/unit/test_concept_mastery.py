"""Unit tests for concept-level learning state and evidence-based mastery tracking."""

from __future__ import annotations

import pytest
from app.core.config import DatabaseSettings, MasterySettings
from app.db.connection import Database
from app.repositories.mastery_repository import MasteryRepository
from app.schemas.enums import EvidenceType, MasteryStatus, PrerequisiteRelation


@pytest.fixture
def in_memory_db() -> Database:
    db = Database(DatabaseSettings(url="sqlite:///:memory:"))
    db.create_schema()
    return db


@pytest.fixture
def mastery_repo(in_memory_db: Database) -> MasteryRepository:
    settings = MasterySettings(
        mastery_threshold=0.80,
        confidence_threshold=0.70,
        min_evidence_count=3,
        evidence_weight=0.35,
        partial_understanding_threshold=0.50,
    )
    return MasteryRepository(in_memory_db, settings=settings)


def test_single_correct_answer_does_not_grant_mastery(mastery_repo: MasteryRepository) -> None:
    """A single correct response must never immediately yield full confidence or MASTERED status."""
    student_id = "student_test_1"
    concept = "Convolution Operation"

    # Record single high-scoring evidence
    ev = mastery_repo.record_evidence(
        student_id=student_id,
        concept=concept,
        evidence_type=EvidenceType.QUIZ_OBJECTIVE,
        score=1.0,
        demonstrated=True,
        confidence=0.95,
        provenance={"test": "single_event"},
    )
    assert ev.id is not None
    assert ev.score == 1.0

    # Fetch updated mastery state (automatically updated by record_evidence)
    mastery = mastery_repo.get_mastery(student_id, concept)
    assert mastery is not None
    assert mastery.attempts == 1
    assert mastery.mastery_score == 1.0
    assert mastery.confidence <= 0.50  # Must be clamped on first attempt
    assert mastery.status != MasteryStatus.MASTERED
    assert mastery.status == MasteryStatus.PARTIALLY_UNDERSTOOD


def test_asymptotic_confidence_and_gradual_mastery(mastery_repo: MasteryRepository) -> None:
    """Three consistent high-scoring demonstrations should achieve MASTERED status."""
    student_id = "student_test_2"
    concept = "Linear Algebra"

    # Attempt 1
    m1 = mastery_repo.update_mastery_from_evidence(
        student_id=student_id,
        concept=concept,
        evidence_score=0.85,
        evidence_confidence=0.90,
    )
    assert m1.attempts == 1
    assert m1.status != MasteryStatus.MASTERED

    # Attempt 2
    m2 = mastery_repo.update_mastery_from_evidence(
        student_id=student_id,
        concept=concept,
        evidence_score=0.90,
        evidence_confidence=0.90,
    )
    assert m2.attempts == 2
    assert m2.status != MasteryStatus.MASTERED
    assert m2.confidence > m1.confidence

    # Attempt 3 (meets min_evidence_count=3, score >= 0.80, confidence >= 0.70)
    m3 = mastery_repo.update_mastery_from_evidence(
        student_id=student_id,
        concept=concept,
        evidence_score=0.95,
        evidence_confidence=0.95,
    )
    assert m3.attempts == 3
    assert m3.mastery_score >= 0.80
    assert m3.confidence >= 0.70
    assert m3.status == MasteryStatus.MASTERED


def test_struggling_student_transitions_to_revision(mastery_repo: MasteryRepository) -> None:
    """Consistent low scores transition a concept into NEEDS_REVISION once min_evidence_count reached."""
    student_id = "student_test_3"
    concept = "Backpropagation"

    for _ in range(3):
        m = mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept=concept,
            evidence_score=0.30,
            evidence_confidence=0.85,
        )

    assert m.attempts == 3
    assert m.mastery_score < 0.50
    assert m.status == MasteryStatus.NEEDS_REVISION


def test_prerequisite_adjacency_graph_and_satisfaction(mastery_repo: MasteryRepository) -> None:
    """Verify concept prerequisite additions and satisfaction checks."""
    student_id = "student_test_4"

    # Add prerequisite: Neural Networks requires Linear Algebra and Calculus
    mastery_repo.add_prerequisite("Neural Networks", "Linear Algebra", PrerequisiteRelation.DIRECT)
    mastery_repo.add_prerequisite("Neural Networks", "Calculus", PrerequisiteRelation.DIRECT)

    prereqs = mastery_repo.get_prerequisites("Neural Networks")
    assert len(prereqs) == 2
    prereq_names = {p.prerequisite_concept for p in prereqs}
    assert "Linear Algebra" in prereq_names
    assert "Calculus" in prereq_names

    # Check initially: both missing
    sat, missing = mastery_repo.check_prerequisites_satisfied(student_id, "Neural Networks")
    assert not sat
    assert set(missing) == {"Linear Algebra", "Calculus"}

    # Master Linear Algebra
    for _ in range(3):
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Linear Algebra",
            evidence_score=0.90,
            evidence_confidence=0.90,
        )

    # Now only Calculus is missing
    sat, missing = mastery_repo.check_prerequisites_satisfied(student_id, "Neural Networks")
    assert not sat
    assert missing == ["Calculus"]

    # Master Calculus
    for _ in range(3):
        mastery_repo.update_mastery_from_evidence(
            student_id=student_id,
            concept="Calculus",
            evidence_score=0.88,
            evidence_confidence=0.90,
        )

    # Now all prerequisites are satisfied
    sat, missing = mastery_repo.check_prerequisites_satisfied(student_id, "Neural Networks")
    assert sat
    assert missing == []


def test_seed_default_curriculum(mastery_repo: MasteryRepository) -> None:
    """Verify seeding default prerequisite curriculum DAG."""
    count = mastery_repo.seed_default_curriculum()
    assert count > 0

    cnn_prereqs = mastery_repo.get_prerequisites("CNN")
    assert len(cnn_prereqs) >= 2
    names = [p.prerequisite_concept for p in cnn_prereqs]
    assert "Neural Networks" in names
    assert "Convolution Operation" in names
