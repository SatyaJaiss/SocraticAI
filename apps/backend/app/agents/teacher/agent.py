"""Teacher agent — generates the lesson/explanation for the current topic."""

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
from app.schemas.domain import Explanation

logger = logging.getLogger(__name__)


class TeacherAgent:
    """Lesson node: produces a validated :class:`Explanation` and persists it."""

    name = "teacher"

    def __init__(self, ctx: AgentContext) -> None:
        self._ctx = ctx

    async def run(self, state: dict) -> dict:
        topic = (state.get("topic") or "general").strip()
        student_id = state.get("student_id") or "anonymous"
        profile = student_profile_from_state(state, self._ctx)

        # Milestone 3: Dynamic pedagogical strategy & explanation mode
        strat_res = None
        strategy_str = "direct_explanation"
        mode_str = "intermediate"
        strategy_prompt_section = ""
        active_misconceptions: list[str] = []

        if getattr(self._ctx, "strategy_selector", None) is not None:
            mastery = (
                self._ctx.mastery_repo.get_mastery(student_id, topic)
                if self._ctx.mastery_repo
                else None
            )
            m_score = mastery.mastery_score if mastery else 0.0
            from app.schemas.enums import MasteryStatus

            m_status = mastery.status if mastery else MasteryStatus.NOT_ATTEMPTED

            if getattr(self._ctx, "misconception_detector", None) is not None:
                active_misconceptions = self._ctx.misconception_detector.get_active_misconceptions(
                    student_id, concept=topic
                )

            prereqs_missing = []
            if self._ctx.mastery_repo:
                _, prereqs_missing = self._ctx.mastery_repo.check_prerequisites_satisfied(
                    student_id, topic
                )

            strat_res = self._ctx.strategy_selector.select(
                message=state.get("user_input") or "",
                student=profile,
                concept=topic,
                mastery_status=m_status,
                mastery_score=m_score,
                has_active_misconceptions=len(active_misconceptions) > 0,
                prerequisites_missing=prereqs_missing,
            )
            strategy_str = strat_res.strategy.value
            mode_str = strat_res.explanation_mode.value

            strategy_prompt_section = (
                f"Tutoring Strategy: {strategy_str}\n"
                f"Explanation Mode: {mode_str}\n"
                f"Pedagogical Reason: {strat_res.reasoning}\n"
            )
            if active_misconceptions:
                strategy_prompt_section += (
                    f"Active Misconceptions to Clarify: {', '.join(active_misconceptions)}\n"
                )
            if prereqs_missing:
                strategy_prompt_section += (
                    f"Missing Prerequisites to Bridge: {', '.join(prereqs_missing)}\n"
                )

        user_prompt = (
            f"Topic: {topic}\n"
            f"Student level: {state.get('level') or profile.level.value}\n"
            f"Learning goal: {state.get('learning_goal') or 'understand the basics'}\n\n"
            f"{strategy_prompt_section}\n"
            f"{profile_prompt_section(profile)}\n\n"
            f"{memory_prompt_section(self._ctx, student_id)}\n\n"
            f"{rag_prompt_section(state)}"
        )
        lesson = await self._ctx.llm.generate_json(
            render_prompt("teacher"),
            user_prompt,
            model_class=Explanation,
        )

        # Persist the lesson and record the topic as covered.
        self._ctx.lesson_repo.save_lesson(student_id, lesson)
        self._ctx.student_repo.add_topic_learned(student_id, lesson.topic)

        # Run citation verification if available
        verification_data = None
        if self._ctx.citation_verifier and student_id != "anonymous":
            rag_context = state.get("rag_context") or {}
            raw_chunks = rag_context.get("retrieved_chunks") or []
            from app.schemas.domain import RetrievedChunk

            chunk_objs = [RetrievedChunk(**c) if isinstance(c, dict) else c for c in raw_chunks]
            full_text = f"{lesson.summary} {lesson.explanation}"
            res = self._ctx.citation_verifier.verify_turn(
                full_text, student_id=student_id, retrieved_chunks=chunk_objs
            )
            verification_data = res.model_dump()

        message = self._format_message(lesson)
        logger.info("Teacher delivered lesson on %r", lesson.topic)
        result_payload = {
            "lesson": lesson.model_dump(),
            "tutoring_strategy": strategy_str,
            "explanation_mode": mode_str,
            "active_misconceptions": active_misconceptions,
            "messages": [{"role": "assistant", "content": message, "node": self.name}],
        }
        if verification_data:
            result_payload["citation_verification"] = verification_data
        return result_payload

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _format_message(lesson: Explanation) -> str:
        blocks = [
            f"### {lesson.topic}",
            lesson.summary,
            "",
            lesson.explanation,
        ]
        if lesson.examples:
            blocks += ["", "**Examples:**"]
            blocks += [f"- {ex}" for ex in lesson.examples]
        if lesson.analogies:
            blocks += ["", "**Analogy:**"]
            blocks += [f"- {an}" for an in lesson.analogies]
        if lesson.recap:
            blocks += ["", f"**Recap:** {lesson.recap}"]
        return "\n".join(blocks)
