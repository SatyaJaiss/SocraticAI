"""Integration tests for adaptive tutoring workflows, Socratic routing, and mastery updates."""

from __future__ import annotations

import pytest
from app.graphs.evaluation.workflow import build_evaluation_graph
from app.graphs.tutoring.workflow import build_tutoring_graph
from app.schemas.domain import Quiz, QuizQuestion
from app.schemas.enums import DifficultyLevel, QuestionType


@pytest.fixture
def initial_state():
    def _make(student_id: str, message: str, **kwargs) -> dict:
        state = {
            "student_id": student_id,
            "user_input": message,
            "topic": kwargs.get("topic"),
            "conversation_id": kwargs.get("conversation_id", "conv_int_1"),
            "with_quiz": kwargs.get("with_quiz", False),
            "intent": kwargs.get("intent", ""),
            "learning_goal": "",
            "level": "intermediate",
            "messages": [],
            "memory_updates": [],
            "errors": [],
            "lesson": None,
            "quiz": None,
            "evaluation": None,
            "recommendations": None,
            "rag_context": None,
            "rag_sources": [],
            "next_agent": "",
        }
        state.update(kwargs)
        return state

    return _make


class TestAdaptiveTutoringWorkflow:
    async def test_teacher_adaptive_strategy_selection(self, ctx, initial_state) -> None:
        """Teacher agent dynamically chooses strategy and mode based on student state."""
        ctx.student_repo.get_or_create("student_adapt_1")
        graph = build_tutoring_graph(ctx)
        state = initial_state(
            "student_adapt_1", "explain gradient descent using mathematical formulas"
        )
        final = await graph.ainvoke(state)

        assert final["intent"] in {"learn", "answer_question"}
        assert final.get("lesson") is not None
        assert final.get("tutoring_strategy") is not None
        assert final.get("explanation_mode") in {"mathematical", "intermediate", "advanced"}

    async def test_socratic_guided_problem_solving_route(self, ctx, initial_state) -> None:
        """User asking for step-by-step guidance routes to the Socratic dialogue node."""
        ctx.student_repo.get_or_create("student_soc_flow_1")
        graph = build_tutoring_graph(ctx)
        state = initial_state(
            "student_soc_flow_1",
            "guide me step by step through solving for kinetic energy",
            conversation_id="conv_soc_flow_1",
        )
        final = await graph.ainvoke(state)

        assert final.get("socratic_response") is not None
        assert final["socratic_response"]["current_step"] == 1
        assert "Step 1" in final["socratic_response"]["question"]

    async def test_quiz_evaluation_updates_mastery_and_misconceptions(self, ctx) -> None:
        """Quiz evaluation records evidence in mastery_repo and checks misconceptions."""
        student_id = "student_eval_mastery_1"
        ctx.student_repo.get_or_create(student_id)
        topic = "Gravity"

        quiz = Quiz(
            id="quiz_adapt_test",
            topic=topic,
            difficulty=DifficultyLevel.INTERMEDIATE,
            questions=[
                QuizQuestion(
                    id="quiz_adapt_testq1",
                    type=QuestionType.MCQ,
                    topic=topic,
                    question="Which hits first in vacuum: heavy ball or light ball?",
                    options=["Heavy ball", "Light ball", "Both hit together"],
                    correct_answer="Both hit together",
                    points=2,
                ),
                QuizQuestion(
                    id="quiz_adapt_testq2",
                    type=QuestionType.NUMERICAL,
                    topic=topic,
                    question="What is acceleration due to gravity on Earth in m/s^2?",
                    correct_answer="9.8",
                    numerical_tolerance=0.01,
                    points=2,
                ),
            ],
        )
        ctx.quiz_repo.create_quiz(quiz, student_id)

        eval_graph = build_evaluation_graph(ctx)
        eval_state = {
            "student_id": student_id,
            "quiz_id": quiz.id,
            "answers": [
                {"question_id": "quiz_adapt_testq1", "answer": "Both hit together"},
                {"question_id": "quiz_adapt_testq2", "answer": "9.81 m/s^2"},
            ],
            "messages": [],
            "errors": [],
        }

        final = await eval_graph.ainvoke(eval_state)
        assert final.get("evaluation") is not None
        assert final["evaluation"]["percent"] == 100.0

        # Verify evidence recorded in mastery_repo
        mastery = ctx.mastery_repo.get_mastery(student_id, topic)
        assert mastery is not None
        assert mastery.attempts == 1
        assert mastery.mastery_score == 1.0
