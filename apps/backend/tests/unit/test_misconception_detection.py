"""Unit tests for evidence-based misconception detection and resolution tracking."""

from __future__ import annotations

import pytest
from app.core.config import DatabaseSettings, MisconceptionSettings
from app.db.connection import Database
from app.repositories.memory_repository import MemoryRepository
from app.repositories.student_repository import StudentRepository
from app.tutoring.misconception_detector import MisconceptionDetector


@pytest.fixture
def in_memory_db() -> Database:
    db = Database(DatabaseSettings(url="sqlite:///:memory:"))
    db.create_schema()
    return db


@pytest.fixture
def detector(in_memory_db: Database) -> MisconceptionDetector:
    memory_repo = MemoryRepository(in_memory_db)
    student_repo = StudentRepository(in_memory_db)
    settings = MisconceptionSettings(
        detection_confidence_threshold=0.75,
        resolution_attempts_required=2,
        prevent_duplicate_active=True,
    )
    return MisconceptionDetector(
        memory_repo=memory_repo,
        student_repo=student_repo,
        settings=settings,
        llm=None,
    )


def test_rule_based_detection_vacuum_freefall(detector: MisconceptionDetector) -> None:
    """Detects classic 'heavier falls faster' misconception."""
    res = detector.detect(
        concept="Gravity",
        student_response="The heavier object with more mass will fall faster and hit first in vacuum.",
    )
    assert len(res) == 1
    assert "heavier objects fall faster" in res[0]["misconception"].lower()
    assert res[0]["confidence"] >= 0.75


def test_rule_based_detection_newtons_third_law(detector: MisconceptionDetector) -> None:
    """Detects 'action force overcomes reaction force' misconception."""
    res = detector.detect(
        concept="Physics",
        student_response="The heavy truck's action force is much greater than the reaction force.",
    )
    assert len(res) == 1
    assert (
        "unequal" in res[0]["misconception"].lower() or "action" in res[0]["misconception"].lower()
    )


def test_rule_based_detection_fraction_addition(detector: MisconceptionDetector) -> None:
    """Detects adding denominators directly in fractions."""
    res = detector.detect(
        concept="Math",
        student_response="To solve 1/2 + 1/3, just add denominators to get 2/5.",
    )
    assert len(res) == 1
    assert "denominators" in res[0]["misconception"].lower()


def test_rule_based_detection_correlation_causation(detector: MisconceptionDetector) -> None:
    """Detects confusing correlation with causation."""
    res = detector.detect(
        concept="Statistics",
        student_response="High correlation definitely implies causation here.",
    )
    assert len(res) == 1
    assert "caus" in res[0]["misconception"].lower()


def test_deduplication_and_resolution_tracking(detector: MisconceptionDetector) -> None:
    """Verifies that duplicate active misconceptions are prevented and resolution is tracked."""
    student_id = "student_misc_1"
    concept = "Gravity"
    misc_text = "Belief that heavier objects fall faster in a vacuum"

    # Register initial misconception
    detector.register_misconception(student_id, concept, misc_text)
    active = detector.get_active_misconceptions(student_id, concept=concept)
    assert len(active) == 1

    # Attempt to register identical active misconception (should be deduplicated)
    detector.register_misconception(student_id, concept, misc_text)
    active_again = detector.get_active_misconceptions(student_id, concept=concept)
    assert len(active_again) == 1

    # Record successful demonstration of understanding
    resolved = detector.record_successful_demonstration(student_id, concept)
    assert resolved

    # Now active misconceptions for this concept should be empty, and resolved should contain it
    active_post = detector.get_active_misconceptions(student_id, concept=concept)
    assert len(active_post) == 0

    resolved_list = detector.get_resolved_misconceptions(student_id)
    assert len(resolved_list) == 1
    assert "Gravity" in resolved_list[0]
