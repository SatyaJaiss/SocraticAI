"""Unit tests for bounded Socratic dialogue and guided problem-solving engine."""

from __future__ import annotations

import pytest
from app.core.config import DatabaseSettings
from app.db.connection import Database
from app.repositories.socratic_repository import SocraticRepository
from app.tutoring.socratic_engine import SocraticEngine


@pytest.fixture
def in_memory_db() -> Database:
    db = Database(DatabaseSettings(url="sqlite:///:memory:"))
    db.create_schema()
    return db


@pytest.fixture
def socratic_repo(in_memory_db: Database) -> SocraticRepository:
    return SocraticRepository(in_memory_db)


@pytest.fixture
def socratic_engine(socratic_repo: SocraticRepository) -> SocraticEngine:
    return SocraticEngine(socratic_repo, llm=None, max_hint_level=4)


def test_start_session_creates_step_one_question(socratic_engine: SocraticEngine) -> None:
    """Starting a session returns step 1 of N without revealing answer."""
    res = socratic_engine.start_session(
        student_id="student_soc_1",
        conversation_id="conv_soc_1",
        concept="Work-Energy Theorem",
        problem_statement="Find velocity when 10 N force acts over 5 m on 2 kg cart.",
        target_solution="W = 50 J. v = sqrt(50) = 7.07 m/s.",
        total_steps=3,
    )

    assert res.session_id.startswith("soc_")
    assert res.current_step == 1
    assert res.total_steps == 3
    assert not res.is_completed
    assert not res.is_stuck
    assert not res.solution_revealed
    assert "Step 1 of 3" in res.question
    assert "7.07" not in res.question  # No answer leakage


def test_step_progression_and_completion(socratic_engine: SocraticEngine) -> None:
    """Step progression through step 1, 2, and 3 concludes the problem successfully."""
    student_id = "student_soc_2"
    conv_id = "conv_soc_2"

    res1 = socratic_engine.start_session(
        student_id=student_id,
        conversation_id=conv_id,
        concept="Work-Energy Theorem",
        problem_statement="Find velocity when 10 N force acts over 5 m on 2 kg cart.",
        target_solution="W = 50 J. v = sqrt(50) = 7.07 m/s.",
        total_steps=3,
    )
    session_id = res1.session_id

    # Step 1 response
    res2 = socratic_engine.process_student_turn(
        session_id=session_id,
        student_input="We should use the Work-Energy Theorem where work equals change in kinetic energy.",
    )
    assert res2.current_step == 2
    assert not res2.is_completed
    assert "Step 2 of 3" in res2.question

    # Step 2 response
    res3 = socratic_engine.process_student_turn(
        session_id=session_id,
        student_input="Work is force times displacement, which gives 10 N * 5 m = 50 Joules.",
    )
    assert res3.current_step == 3
    assert not res3.is_completed
    assert "Step 3 of 3" in res3.question

    # Step 3 response (final)
    res4 = socratic_engine.process_student_turn(
        session_id=session_id,
        student_input="Setting 50 = 0.5 * 2 * v^2 gives v^2 = 50 so v is approximately 7.07 m/s.",
    )
    assert res4.is_completed
    assert "Excellent work" in res4.feedback
    assert res4.current_step == 3


def test_progressive_hint_escalation_and_stuck_detection(socratic_engine: SocraticEngine) -> None:
    """Progressive hint escalation strictly enforces Levels 1 -> 2 -> 3 -> 4."""
    student_id = "student_soc_3"
    conv_id = "conv_soc_3"

    res = socratic_engine.start_session(
        student_id=student_id,
        conversation_id=conv_id,
        concept="Kinematics",
        problem_statement="Calculate time taken to fall 20m under g=10.",
        target_solution="t = sqrt(2*h/g) = sqrt(40/10) = 2 seconds.",
        total_steps=2,
    )
    session_id = res.session_id

    # Level 1 hint
    h1 = socratic_engine.escalate_hint(session_id, reason="Student asked for hint")
    assert h1.hint_level == 1
    assert "Conceptual Direction" in h1.feedback
    assert not h1.is_stuck
    assert not h1.solution_revealed
    assert "2 seconds" not in (h1.hint or "")

    # Level 2 hint
    h2 = socratic_engine.escalate_hint(session_id, reason="Still not sure")
    assert h2.hint_level == 2
    assert "Formula Structure" in h2.feedback
    assert not h2.is_stuck
    assert not h2.solution_revealed

    # Level 3 hint
    h3 = socratic_engine.escalate_hint(session_id, reason="Need more help")
    assert h3.hint_level == 3
    assert "Partial Solution" in h3.feedback
    assert not h3.is_stuck
    assert not h3.solution_revealed

    # Level 4 hint (max level: solution revealed and student marked stuck)
    h4 = socratic_engine.escalate_hint(session_id, reason="Completely stuck")
    assert h4.hint_level == 4
    assert h4.is_stuck
    assert h4.solution_revealed
    assert "2 seconds" in (h4.hint or "")
