"""Deterministic offline LLM for the ``demo`` provider.

The demo client implements the same interface as :class:`LLMClient` but never
touches the network. It inspects the requested Pydantic schema and returns
plausible, topic-aware content so the full tutoring pipeline (graph, RAG,
persistence, dashboard) can be exercised end-to-end without an API key -- ideal
for first-run demos, CI and offline development.
"""

from __future__ import annotations

import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import QuizComposition
from app.core.exceptions import LLMOutputParsingError
from app.schemas.enums import ChatIntent, DifficultyLevel, QuestionType, StudentLevel

T = TypeVar("T", bound=BaseModel)

_GENERIC_REPLIES = [
    "That's a great question. In SocraticAI, I break topics into simple ideas "
    "and build your understanding step by step.",
    "Let's learn that together. I'll start with the fundamentals, add examples, "
    "and then we can quiz what you've learned.",
]


class DemoLLMClient:
    """Schema-driven deterministic responses (never calls an external API)."""

    provider = "demo"

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    # ------------------------------------------------------------ generate --
    async def generate(self, system: str, user: str, *, temperature: float | None = None) -> str:
        return (
            f"Here is a concise, friendly explanation based on your message: "
            f"«{self._first_sentence(user)}» — in demo mode no live model is "
            f"used. Configure an LLM API key for fully-generated responses."
        )

    # -------------------------------------------------------- generate_json --
    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        model_class: type[T],
        temperature: float | None = None,
    ) -> T:
        builder = getattr(self, f"_demo{model_class.__name__.lower()}", None)
        if builder is None:
            raise LLMOutputParsingError(
                f"Demo provider has no generator for {model_class.__name__}"
            )
        try:
            return model_class.model_validate(builder(user))
        except ValidationError as exc:  # pragma: no cover - defensive
            raise LLMOutputParsingError(
                f"Demo output failed {model_class.__name__} validation: {exc}"
            ) from exc

    # -------------------------------------------------------------- helpers --
    @staticmethod
    def _first_sentence(text: str) -> str:
        """Return the first meaningful sentence of ``text``.

        Prompt-structure labels (``Student message:``, ``Assistant response:``,
        etc.) are skipped and the text is collapsed to a single line so a stored
        memory summary never embeds prompt scaffolding or multi-line fragments
        that later heuristics would misread as real content.
        """
        stripped = text.strip()
        if not stripped:
            return "the topic"
        for line in stripped.splitlines():
            ln = line.strip()
            if not ln:
                continue
            if re.match(r"^[A-Za-z ]+:$", ln):
                continue  # structural label, e.g. "Student message:"
            return ln.split(".", 1)[0].strip() or "the topic"
        return "the topic"

    @staticmethod
    def _prefix_value(lines: list[str], prefix: str) -> str:
        """Return the value after a ``prefix:`` line, or an empty string."""
        for ln in lines:
            if ln.lower().startswith(prefix):
                return ln.split(":", 1)[1].strip().strip("\"' —:-")
        return ""

    @staticmethod
    def _student_message(text: str) -> str | None:
        """Extract the student's raw message from an assembled prompt.

        Prompts are built as ``Student message:\\n<body>`` followed by profile
        and memory context blocks. Keyword heuristics must run against the
        *body* only — the context can contain words like "quiz" from history
        and would otherwise skew classification.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if ln.lower().startswith("student message:"):
                if i + 1 < len(lines):
                    return lines[i + 1]
                return None
        return None

    @classmethod
    def _sanitize_topic(cls, text: str) -> str:
        """Sanitize an extracted topic string:
        - Strip memory tags like (conversation_summary), (concept), (fact), (entity).
        - Strip conversational prefixes/question stems (e.g. 'what is', 'explain', 'tell me about').
        - Strip trailing and leading punctuation (?, !, ., quotes, bullets).
        - Ensure clean capitalization (e.g. 'what is gateway?' -> 'Gateway').
        """
        if not text:
            return "General"

        # Remove internal memory tags e.g. (conversation_summary), (concept)
        cleaned = re.sub(
            r"[\(\[](?:conversation_summary|concept|fact|entity|memory)[\)\]]",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove leading bullets, list markers, dashes
        cleaned = re.sub(r"^\s*[-*•\d\.\)]\s*", "", cleaned)

        # Remove common conversational / question stems (longer phrases first)
        stems = [
            r"^(?:can\s+you\s+)?(?:could\s+you\s+)?(?:please\s+)?(?:explain|describe|define)\s+(?:to\s+me\s+)?(?:about\s+)?(?:what\s+is\s+(?:an?|the)?\s*)?",
            r"^(?:tell|teach)\s+me\s+about\s+",
            r"^(?:i\s+want\s+to\s+(?:learn|know)\s+(?:about\s+)?)",
            r"^(?:give\s+me\s+an?\s+overview\s+of\s+)",
            r"^(?:give\s+an?\s+overview\s+of\s+)",
            r"^(?:what\s+is\s+(?:an?|the)?\s*)",
            r"^(?:what\s+are\s+(?:the)?\s*)",
            r"^(?:how\s+(?:does|do|can|to)\s+(?:an?|the)?\s*)",
            r"^(?:why\s+(?:is|are|does|do)\s+(?:an?|the)?\s*)",
            r"^(?:what\s+do\s+you\s+mean\s+by\s+)",
        ]
        for pattern in stems:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Strip remaining punctuation from ends: quotes, periods, questions, dashes
        cleaned = cleaned.strip(" \t\n\r?!.—:\"'`*")
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        if len(cleaned) > 60:
            cleaned = cleaned[:60].rsplit(" ", 1)[0].strip(" \t\n\r?!.—:\"'`*")

        if not cleaned:
            return "General"

        # Clean capitalization: ensure leading letter is uppercase while preserving acronyms/casing
        return cleaned[0].upper() + cleaned[1:]

    def _topic(self, text: str) -> str:
        """Extract a short topic string from the full assembled prompt.

        Strategy:
        1. Look for an explicit ``Topic: X`` line (embedded by teacher/quiz/evaluation).
        2. Look for the ``Student message:`` body (planner).
        3. Look for a ``Weak concepts: X`` line (recommendation).
        4. Fall back to the last non-trivial line.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # 1) Explicit "Topic: X" line
        topic = self._prefix_value(lines, "topic:")
        if topic:
            return self._sanitize_topic(topic)
        # 2) The student-message body (line after "Student message:")
        body = self._student_message(text)
        if body:
            return self._sanitize_topic(body)
        # 3) "Weak concepts:" line value (recommendation context) — the value is
        #    "none" / "none identified" when there are no weak areas, so any
        #    value starting with "none" must be treated as absent.
        weak = self._prefix_value(lines, "weak concepts:")
        if weak and not weak.lower().startswith("none"):
            return self._sanitize_topic(weak.split(",")[0])
        # 4) Fallback: last non-trivial line
        if not lines:
            return "General"
        candidate = lines[-1].strip("\"' —:-")
        candidate = re.sub(r"\s{2,}", " ", candidate)
        return self._sanitize_topic(candidate)

    def _intent(self, user: str) -> ChatIntent:
        message = (self._student_message(user) or user).lower()
        if any(w in message for w in ("quiz", "test me", "practice", "exercise", "mcq")):
            return ChatIntent.PRACTICE
        if any(w in message for w in ("?", "what is", "explain", "why", "how", "answer")):
            return ChatIntent.ANSWER_QUESTION
        return ChatIntent.LEARN

    # ------------------------------------------------------------ builders --
    def _demoplanneroutput(self, user: str) -> dict:
        topic = self._topic(user)
        intent = self._intent(user)
        return {
            "intent": intent.value,
            "topic": topic,
            "learning_goal": f"Understand the fundamentals of {topic}",
            "level": StudentLevel.BEGINNER.value,
            "prerequisites": [],
        }

    def _demoexplanation(self, user: str) -> dict:
        topic = self._topic(user).rstrip(".?! ")
        return {
            "topic": topic,
            "summary": f"A friendly overview of {topic}.",
            "explanation": (
                f"{topic} is easiest to learn when you break it into small, "
                f"connected ideas. Start with the big picture, then drill into "
                f"each detail with examples and analogies."
            ),
            "examples": [
                f"Example 1: a simple, everyday illustration of {topic}.",
                f"Example 2: a step-by-step worked case for {topic}.",
            ],
            "analogies": [
                f"Think of {topic} like learning to ride a bicycle — balance first, speed later.",
            ],
            "recap": (
                f"To master {topic}, remember the key idea, try the examples "
                f"yourself, and take a short quiz to lock it in."
            ),
        }

    def _demoquiz(self, user: str) -> dict:
        topic = self._topic(user).rstrip(".?! ")
        questions: list[dict] = []
        qindex = 0

        def question(qtype: QuestionType) -> dict:
            nonlocal qindex
            qindex += 1
            base = {
                "id": f"demoq{qindex}",
                "type": qtype.value,
                "topic": topic,
                "points": 1,
                "explanation": f"The key point about {topic}.",
            }
            if qtype == QuestionType.MCQ:
                base.update(
                    {
                        "question": f"Which statement about {topic} is correct?",
                        "options": [
                            f"Statement A about {topic}",
                            f"Statement B about {topic}",
                            f"Statement C about {topic}",
                            f"Statement D about {topic}",
                        ],
                        "correct_answer": f"Statement A about {topic}",
                    }
                )
            elif qtype == QuestionType.NUMERICAL:
                base.update(
                    {
                        "question": (
                            f"Using the basic rule for {topic}, compute the value of 2 + 3."
                        ),
                        "options": [],
                        "correct_answer": "5",
                    }
                )
            else:
                base.update(
                    {
                        "question": (
                            f"In your own words, summarise one key idea of {topic} "
                            f"and give an example."
                        ),
                        "options": [],
                        "correct_answer": (
                            f"A correct summary of {topic} mentions the central "
                            f"idea and a concrete example."
                        ),
                    }
                )
            return base

        for _ in range(QuizComposition.MCQ_COUNT):
            questions.append(question(QuestionType.MCQ))
        for _ in range(QuizComposition.NUMERICAL_COUNT):
            questions.append(question(QuestionType.NUMERICAL))
        questions.append(question(QuestionType.SUBJECTIVE))

        return {
            "id": "demo_quiz",
            "topic": topic,
            "difficulty": DifficultyLevel.BEGINNER.value,
            "questions": questions,
        }

    def _demosubjectivegrade(self, user: str) -> dict:
        topic = self._topic(user)
        return {
            "score": 0.8,
            "feedback": (
                "Good attempt. Revisit the core idea, add a concrete example, "
                "and retry the subjective question to strengthen your answer."
            ),
            "weak_concepts": [topic],
            "revision_topics": [topic],
            "next_lesson": f"Apply {topic} to a real-world example",
        }

    def _demomemoryextraction(self, user: str) -> dict:
        topic = self._topic(user)
        return {
            "facts": [
                {
                    "fact_type": "concept",
                    "content": f"Student engaged with the topic {topic}.",
                    "importance": 0.7,
                },
                {
                    "fact_type": "conversation_summary",
                    "content": self._first_sentence(user),
                    "importance": 0.5,
                },
            ]
        }

    def _demorecommendation(self, user: str) -> dict:
        topic = self._topic(user).rstrip(".?! ")
        return {
            "next_topic": f"A practical application of {topic}",
            "rationale": (
                f"You have started {topic}; applying it next reinforces the "
                f"concepts and builds confidence."
            ),
            "revision_schedule": [
                f"Day 1: re-read the {topic} recap and examples",
                f"Day 3: retake the {topic} quiz",
                f"Day 7: revisit {topic} with a practice problem",
            ],
            "daily_plan": [
                f"Review {topic} for 15 minutes",
                "Do one worked example",
                "Summarise the key idea in your own words",
            ],
            "weak_areas": [topic],
            "suggested_quiz_topics": [topic],
        }

    @property
    def settings(self) -> Any:
        return self._settings
