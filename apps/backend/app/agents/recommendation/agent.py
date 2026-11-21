"""Recommendation agent — proposes the student's next learning step."""

from __future__ import annotations

import logging

from app.agents.base import (
    memory_prompt_section,
    profile_prompt_section,
    student_profile_from_state,
)
from app.agents.context import AgentContext
from app.llm.prompts.loader import render_prompt
from app.schemas.domain import Recommendation

logger = logging.getLogger(__name__)


class RecommendationAgent:
    """Recommendation node: produces a :class:`Recommendation` and persists it."""

    name = "recommendation"

    def __init__(self, ctx: AgentContext) -> None:
        self._ctx = ctx

    async def run(self, state: dict) -> dict:
        student_id = state.get("student_id") or "anonymous"
        profile = student_profile_from_state(state, self._ctx)
        concept_scores = self._ctx.student_repo.list_concept_scores(student_id)
        weak = list(profile.weak_concepts or []) or [
            c.concept for c in concept_scores if c.proficiency < 0.6
        ]
        evaluation = state.get("evaluation") or {}

        score_lines = (
            "\n".join(
                f"- {s.concept}: {s.proficiency:.0%} ({s.attempts} attempts)"
                for s in concept_scores[:10]
            )
            or "- (no concept scores yet)"
        )

        prereq_section = ""
        if getattr(self._ctx, "prerequisite_engine", None) is not None:
            prereq_recs = self._ctx.prerequisite_engine.generate_recommendations(
                student_id, current_topic=state.get("topic") or ""
            )
            if prereq_recs:
                prereq_section = (
                    "Prerequisite Dependency Graph Recommendations:\n"
                    + "\n".join(
                        f"- {r.concept} (Priority {r.priority}, Action: {r.action_type}): {r.reason}"
                        for r in prereq_recs[:4]
                    )
                    + "\n\n"
                )

        current_topic = (state.get("topic") or "General Studies").strip()
        user_prompt = (
            f"Topic: {current_topic}\n\n"
            f"{profile_prompt_section(profile)}\n\n"
            f"{prereq_section}"
            f"Concept scores:\n{score_lines}\n\n"
            f"Weak concepts: {', '.join(weak) or 'none identified'}\n"
            f"Latest quiz: {evaluation.get('percent') if evaluation else 'none'}"
            f" ({evaluation.get('weak_concepts') if evaluation else ''})\n"
            f"Feedback: {evaluation.get('feedback') or 'none'}\n\n"
            f"{memory_prompt_section(self._ctx, student_id)}"
        )
        try:
            rec = await self._ctx.llm.generate_json(
                render_prompt("recommendation"),
                user_prompt,
                model_class=Recommendation,
            )
        except Exception as e:
            logger.warning("LLM recommendation failed: %s; falling back to graph engine.", e)
            if getattr(self._ctx, "prerequisite_engine", None) is not None:
                rec = self._ctx.prerequisite_engine.build_legacy_recommendation(
                    student_id, current_topic=state.get("topic") or ""
                )
            else:
                raise
        self._ctx.memory_repo.save_recommendation(student_id, rec)

        message = self._format_message(rec)
        logger.info("Recommendation agent suggested next topic: %r", rec.next_topic)
        return {
            "recommendations": rec.model_dump(),
            "messages": [{"role": "assistant", "content": message, "node": self.name}],
        }

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _format_message(rec: Recommendation) -> str:
        """Render a concise pointer in chat — full plan is viewed on the Learning Dashboard."""
        return (
            f"💡 **Recommended next step:** {rec.next_topic}. "
            f"View your full study plan on the **Learning Dashboard**."
        )
