"""Canonical enumerations used across SocraticAI."""

from __future__ import annotations

from enum import StrEnum


class StudentLevel(StrEnum):
    """Student proficiency level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LearningStyle(StrEnum):
    """Preferred learning modality (VARK-style)."""

    VISUAL = "visual"
    AUDITORY = "auditory"
    READING_WRITING = "reading_writing"
    KINESTHETIC = "kinesthetic"


class LearningSpeed(StrEnum):
    """Self-reported pace at which the student learns new topics."""

    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


# Auto-adaptation policy: numeric cut-offs used to step difficulty up/down.
PROMOTE_THRESHOLD = 0.8  # mean score >= this -> step difficulty up
DEMOTE_THRESHOLD = 0.5  # mean score <= this -> step difficulty down


class DifficultyLevel(StrEnum):
    """Quiz difficulty. Ordered ladder used for auto-adaptation."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @classmethod
    def ladder(cls) -> tuple[DifficultyLevel, ...]:
        """Return difficulty levels ordered easiest -> hardest."""
        return (cls.BEGINNER, cls.INTERMEDIATE, cls.ADVANCED)

    def promoted(self) -> DifficultyLevel:
        """Next-harder level (clamped at the top of the ladder)."""
        ladder = self.ladder()
        idx = min(ladder.index(self) + 1, len(ladder) - 1)
        return ladder[idx]

    def demoted(self) -> DifficultyLevel:
        """Next-easier level (clamped at the bottom of the ladder)."""
        ladder = self.ladder()
        idx = max(ladder.index(self) - 1, 0)
        return ladder[idx]


class QuestionType(StrEnum):
    """Kinds of question a quiz can contain."""

    MCQ = "mcq"
    NUMERICAL = "numerical"
    SUBJECTIVE = "subjective"


class MemoryFactType(StrEnum):
    """Categorises facts stored in long-term memory."""

    PROFILE = "profile"
    PREFERENCE = "preference"
    CONCEPT = "concept"
    STRENGTH = "strength"
    MISTAKE = "mistake"
    CONVERSATION_SUMMARY = "conversation_summary"
    RECOMMENDATION = "recommendation"


class DocumentStatus(StrEnum):
    """Lifecycle of an uploaded document through the ingestion pipeline."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ChatIntent(StrEnum):
    """Intent classification produced by the Planner agent."""

    LEARN = "learn"
    ANSWER_QUESTION = "answer_question"
    PRACTICE = "practice"
    UPLOAD = "upload"
    GENERAL = "general"

