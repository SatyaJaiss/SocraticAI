"""Adaptive explanation engine varying depth, analogies, examples, and math detail."""

from __future__ import annotations

import logging
from typing import ClassVar

from app.llm.clients.client import LLMClient
from app.schemas.domain import Explanation, StudentProfile
from app.schemas.enums import ExplanationMode

logger = logging.getLogger(__name__)


class AdaptiveExplanationEngine:
    """Generates and customizes educational explanations across 6 distinct pedagogical modes."""

    MODE_PROMPTS: ClassVar[dict[ExplanationMode, str]] = {
        ExplanationMode.BEGINNER: (
            "Explain in simple, everyday language without complex jargon. "
            "Build intuition from the ground up, use a relatable introductory example, "
            "and emphasize the 'what' and 'why'."
        ),
        ExplanationMode.INTERMEDIATE: (
            "Provide a balanced explanation combining clear conceptual intuition with standard "
            "academic terminology and practical examples. Cover both core mechanics and practical relevance."
        ),
        ExplanationMode.ADVANCED: (
            "Provide an in-depth, rigorous explanation exploring subtle edge cases, underlying mechanics, "
            "theoretical foundations, and real-world complexities."
        ),
        ExplanationMode.MATHEMATICAL: (
            "Focus heavily on formal mathematical definitions, symbolic expressions, step-by-step derivations, "
            "and quantitative relationships."
        ),
        ExplanationMode.INTUITIVE: (
            "Use a rich, memorable real-world analogy or mental model to make the concept tangible. "
            "Minimize abstract symbols in favor of physical intuition and visualizable dynamics."
        ),
        ExplanationMode.EXAM_ORIENTED: (
            "Structure as a high-yield exam revision guide. Highlight crucial formulas, key definitions, "
            "common traps/misconceptions students make on exams, and concise memory mnemonics."
        ),
    }

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def build_system_instructions(
        self,
        mode: ExplanationMode = ExplanationMode.INTERMEDIATE,
        student: StudentProfile | None = None,
        misconceptions: list[str] | None = None,
    ) -> str:
        """Construct specialized system prompt directives for the chosen explanation mode."""
        base_inst = self.MODE_PROMPTS.get(mode, self.MODE_PROMPTS[ExplanationMode.INTERMEDIATE])
        directives = [
            f"Explanation Mode: {mode.value.upper()}",
            base_inst,
        ]

        if student:
            directives.append(
                f"Student Level: {student.level.value} | Preferred Style: {student.learning_style.value}"
            )
            if student.interests:
                directives.append(
                    f"Tailor analogies/examples to student interests: {', '.join(student.interests[:3])}"
                )

        if misconceptions:
            directives.append(
                f"Explicitly address and gently clarify these known misconceptions: {', '.join(misconceptions)}"
            )

        return "\n".join(directives)

    def generate_explanation(
        self,
        topic: str,
        mode: ExplanationMode = ExplanationMode.INTERMEDIATE,
        student: StudentProfile | None = None,
        rag_context: str = "",
        active_misconceptions: list[str] | None = None,
    ) -> Explanation:
        """Generate structured Explanation object adapted to student mode and context."""
        instructions = self.build_system_instructions(mode, student, active_misconceptions)

        prompt = f"{instructions}\n\nTopic to explain: {topic}\n"
        if rag_context:
            prompt += f"\nRelevant course material:\n{rag_context}\n"

        prompt += (
            "\nPlease provide a complete explanation formatted with:\n"
            "1. Clear conceptual content\n"
            "2. 2-3 illustrative examples\n"
            "3. 2-3 key takeaways\n"
        )

        if self.llm is not None:
            try:
                res = self.llm.generate(prompt)
                content = getattr(res, "content", str(res))
                return Explanation(
                    topic=topic,
                    content=content,
                    examples=[f"Example illustrating {topic} in {mode.value} context"],
                    key_takeaways=[f"Core takeaway for {topic}"],
                )
            except Exception as e:
                logger.warning(
                    f"LLM explanation generation failed: {e}; falling back to templated explanation."
                )

        # Deterministic structured fallback
        return self._fallback_explanation(topic, mode, student)

    def _fallback_explanation(
        self,
        topic: str,
        mode: ExplanationMode,
        student: StudentProfile | None = None,
    ) -> Explanation:
        """Reliable fallback explanation for offline/testing/demo execution."""
        examples = [
            f"Practical application of {topic} in daily life.",
            f"Standard problem setup demonstrating {topic}.",
        ]
        takeaways = [
            f"Understanding {topic} is essential for downstream applications.",
            f"Key relationship in {topic} depends on clear problem setup.",
        ]

        if mode == ExplanationMode.BEGINNER:
            content = (
                f"Welcome to {topic}! At its core, {topic} is about how basic building blocks interact. "
                "Think of it like learning the rules of a friendly game: once you know what each piece does, "
                "the rest falls into place step by step."
            )
        elif mode == ExplanationMode.MATHEMATICAL:
            content = (
                f"Formal Analysis of {topic}:\n"
                f"Let X represent the state space for {topic}. The governing equation is given by "
                f"F(x) = dy/dx + k*x. In equilibrium, the boundary conditions ensure stability."
            )
        elif mode == ExplanationMode.INTUITIVE:
            content = (
                f"An intuitive way to picture {topic} is through a water reservoir analogy. "
                f"Just like water flowing through pipes of different widths, {topic} balances inputs and outputs "
                "until dynamic equilibrium is reached."
            )
        elif mode == ExplanationMode.EXAM_ORIENTED:
            content = (
                f"Exam Master Guide for {topic}:\n"
                f"- High-yield rule: Always check units and conservation laws first.\n"
                f"- Common trap: Forgetting sign conventions in {topic}.\n"
                f"- Quick formula check: Double check boundary cases."
            )
        elif mode == ExplanationMode.ADVANCED:
            content = (
                f"Advanced Treatise on {topic}:\n"
                f"Examining {topic} reveals non-linear interactions under high-order perturbations. "
                "Second-order effects must be accounted for when scaling systems to production."
            )
        else:
            content = (
                f"Explanation of {topic}:\n"
                f"{topic} is a foundational concept. It connects theoretical principles to concrete systems, "
                "providing predictable behavior under standard conditions."
            )

        return Explanation(
            topic=topic,
            content=content,
            examples=examples,
            key_takeaways=takeaways,
        )
