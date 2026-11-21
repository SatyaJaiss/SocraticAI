"""Quiz agent — generates a fixed-composition quiz for the current topic."""

from __future__ import annotations

import logging

from app.agents.base import (
    memory_prompt_section,
    profile_prompt_section,
    rag_prompt_section,
    student_profile_from_state,
)
from app.agents.context import AgentContext
from app.llm.prompts.loader import render_prompt
from app.schemas.domain import Quiz
from app.schemas.enums import QuestionType
from app.utils.helpers import generate_id

logger = logging.getLogger(__name__)


class QuizAgent:
    """Quiz node: produces a validated :class:`Quiz` and persists it."""

    name = "quiz"

    def __init__(self, ctx: AgentContext) -> None:
        self._ctx = ctx

    async def run(self, state: dict) -> dict:
        topic = (state.get("topic") or "general").strip()
        student_id = state.get("student_id") or "anonymous"
        profile = student_profile_from_state(state, self._ctx)

        user_prompt = (
            f"Topic: {topic}\n"
            f"Requested difficulty: {profile.preferred_difficulty.value}\n"
            f"Student level: {state.get('level') or profile.level.value}\n\n"
            f"{profile_prompt_section(profile)}\n\n"
            f"{memory_prompt_section(self._ctx, student_id)}\n\n"
            f"{rag_prompt_section(state)}"
        )
        quiz = await self._ctx.llm.generate_json(
            render_prompt("quiz"),
            user_prompt,
            model_class=Quiz,
        )

        # Guarantee a unique id per generation (demo/provider ids may collide).
        quiz.id = generate_id("quiz")

        self._ctx.quiz_repo.create_quiz(quiz, student_id)
        # Reload from the repo so question ids match what the evaluation agent
        # will load when grading a submission ({quiz_id}q{idx}). Returning the
        # generator's own ids (demoq1, ...) would make every submitted answer
        # miss when the quiz is later graded.
        quiz = self._ctx.quiz_repo.get_quiz(quiz.id) or quiz
        message = self._format_message(quiz)
        logger.info("Quiz agent generated %d questions on %r", len(quiz.questions), topic)
        return {
            "quiz": quiz.model_dump(),
            "messages": [{"role": "assistant", "content": message, "node": self.name}],
        }

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _format_message(quiz: Quiz) -> str:
        """Render a concise, friendly notification for chat (full quiz is in the Quiz tab)."""
        count = len(quiz.questions)
        article = "an" if str(count).startswith(("8", "11", "18")) else "a"
        difficulty_label = (
            quiz.difficulty.value
            if hasattr(quiz.difficulty, "value")
            else str(quiz.difficulty)
        )
        return (
            f"📝 I've prepared {article} **{count}-question practice quiz** on **{quiz.topic}** "
            f"({difficulty_label} level).\n\n"
            f"Head over to the **Practice Quiz** tab to test your knowledge!"
        )
