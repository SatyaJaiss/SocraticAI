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
    EXPERT = "expert"

    @classmethod
    def ladder(cls) -> tuple[DifficultyLevel, ...]:
        """Return difficulty levels ordered easiest -> hardest."""
        return (cls.BEGINNER, cls.INTERMEDIATE, cls.ADVANCED, cls.EXPERT)

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
    TRUE_FALSE = "true_false"
    CONCEPTUAL = "conceptual"
    APPLICATION = "application"
    SCENARIO = "scenario"


class TutoringStrategy(StrEnum):
    """Pedagogical teaching strategy dynamically chosen by SocraticAI."""

    DIRECT_EXPLANATION = "direct_explanation"
    STEP_BY_STEP = "step_by_step"
    SOCRATIC_QUESTIONING = "socratic_questioning"
    GUIDED_PROBLEM_SOLVING = "guided_problem_solving"
    HINT_BASED = "hint_based"
    CONCEPTUAL_ANALOGY = "conceptual_analogy"
    WORKED_EXAMPLE = "worked_example"
    KNOWLEDGE_CHECK = "knowledge_check"
    REVISION_RECAP = "revision_recap"


class ExplanationMode(StrEnum):
    """Contextual depth and style of an explanation."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MATHEMATICAL = "mathematical"
    INTUITIVE = "intuitive"
    EXAM_ORIENTED = "exam_oriented"


class MasteryStatus(StrEnum):
    """Categorical state of a student's concept mastery."""

    NOT_ATTEMPTED = "not_attempted"
    ATTEMPTED = "attempted"
    PARTIALLY_UNDERSTOOD = "partially_understood"
    MASTERED = "mastered"
    NEEDS_REVISION = "needs_revision"


class EvidenceType(StrEnum):
    """Provenance and type of evidence supporting a mastery update."""

    QUIZ_OBJECTIVE = "quiz_objective"
    QUIZ_SUBJECTIVE = "quiz_subjective"
    SOCRATIC_DIALOGUE = "socratic_dialogue"
    PROBLEM_SOLVING = "problem_solving"
    DIRECT_ASSERTION = "direct_assertion"


class PrerequisiteRelation(StrEnum):
    """Type of dependency between educational concepts."""

    DIRECT = "direct"
    WEAK = "weak"
    CO_REQUISITE = "co_requisite"


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
