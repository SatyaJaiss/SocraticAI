"""Unit tests for adaptive quiz grading across objective and rubric subjective formats."""

from __future__ import annotations

import pytest
from app.core.config import AssessmentSettings
from app.schemas.domain import QuizQuestion, SubjectiveRubric
from app.schemas.enums import QuestionType
from app.tutoring.quiz_engine import AdaptiveQuizEngine


@pytest.fixture
def quiz_engine() -> AdaptiveQuizEngine:
    settings = AssessmentSettings(
        numerical_relative_tolerance=0.01,
        numerical_absolute_tolerance=1e-4,
        subjective_passing_score=0.70,
    )
    return AdaptiveQuizEngine(assessment_settings=settings, llm=None)


def test_mcq_evaluation_deterministic(quiz_engine: AdaptiveQuizEngine) -> None:
    """MCQ matching handles option letter, text matching, and case insensitivity."""
    q = QuizQuestion(
        id="q1",
        type=QuestionType.MCQ,
        topic="Biology",
        question="What is the powerhouse of the cell?",
        options=["Nucleus", "Ribosome", "Mitochondria", "Golgi apparatus"],
        correct_answer="Mitochondria",
        points=2,
    )

    # Correct text match
    ok, score, _, _ = quiz_engine.grade_question(q, "Mitochondria")
    assert ok
    assert score == 2.0

    # Correct letter index (C)
    ok, score, _, _ = quiz_engine.grade_question(q, "C")
    assert ok
    assert score == 2.0

    # Incorrect answer
    ok, score, _, _ = quiz_engine.grade_question(q, "A")
    assert not ok
    assert score == 0.0


def test_true_false_evaluation(quiz_engine: AdaptiveQuizEngine) -> None:
    """True/False deterministic normalization handles varied aliases."""
    q = QuizQuestion(
        id="q2",
        type=QuestionType.TRUE_FALSE,
        topic="Physics",
        question="Light travels faster than sound in air.",
        correct_answer="True",
        points=1,
    )

    for valid_true in ["True", "true", "T", "1", "YES", "yes"]:
        ok, score, _, _ = quiz_engine.grade_question(q, valid_true)
        assert ok
        assert score == 1.0

    for invalid_false in ["False", "false", "F", "0", "no"]:
        ok, score, _, _ = quiz_engine.grade_question(q, invalid_false)
        assert not ok
        assert score == 0.0


def test_numerical_evaluation_tolerances(quiz_engine: AdaptiveQuizEngine) -> None:
    """Numerical grading respects relative tolerance (1%) and extracts floats from text."""
    q = QuizQuestion(
        id="q3",
        type=QuestionType.NUMERICAL,
        topic="Math",
        question="Calculate 100.0 * 1.005",
        correct_answer="100.5",
        numerical_tolerance=0.01,  # 1%
        points=3,
    )

    # Exact
    ok, score, _, _ = quiz_engine.grade_question(q, "100.5")
    assert ok
    assert score == 3.0

    # Within 1% (100.8 vs 100.5 is 0.3/100.5 = 0.29% < 1%)
    ok, score, _, _ = quiz_engine.grade_question(q, "100.8")
    assert ok
    assert score == 3.0

    # Embedded in unit string ("approx 100.6 kg")
    ok, score, _, _ = quiz_engine.grade_question(q, "approx 100.6 kg")
    assert ok
    assert score == 3.0

    # Out of tolerance (103.5 is ~3% off)
    ok, score, _, _ = quiz_engine.grade_question(q, "103.5")
    assert not ok
    assert score == 0.0


def test_subjective_rubric_grading(quiz_engine: AdaptiveQuizEngine) -> None:
    """Subjective rubric evaluation weights conceptual correctness, reasoning, and completeness."""
    rubric = SubjectiveRubric(
        conceptual_correctness_weight=0.40,
        reasoning_weight=0.30,
        completeness_weight=0.30,
        key_points=["variance", "bias", "generalization"],
    )
    q = QuizQuestion(
        id="q4",
        type=QuestionType.CONCEPTUAL,
        topic="Machine Learning",
        question="Explain the difference between overfitting and underfitting.",
        correct_answer="Overfitting has high variance; underfitting has high bias.",
        rubric=rubric,
        points=4,
    )

    # Detailed, reasoned answer
    good_answer = (
        "Overfitting occurs when a model captures noise and has high variance, causing poor generalization. "
        "In contrast, underfitting happens because the model is too simple with high bias."
    )
    ok, score, feedback, meta = quiz_engine.grade_question(q, good_answer)
    assert ok
    assert feedback
    assert score >= 2.8  # >= 70% of 4 points
    assert meta["passed"]

    # Incomplete one-liner
    poor_answer = "One is big and one is small."
    ok, score, _feedback, meta = quiz_engine.grade_question(q, poor_answer)
    assert not ok
    assert score < 2.8
    assert not meta["passed"]
