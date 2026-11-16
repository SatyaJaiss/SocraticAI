"""Pydantic domain models and API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    DifficultyLevel,
    LearningSpeed,
    LearningStyle,
    MemoryFactType,
    QuestionType,
    StudentLevel,
)


# --------------------------------------------------------------------------- #
# Student
# --------------------------------------------------------------------------- #
class StudentProfile(BaseModel):
    """Stable + evolving attributes of a learner."""

    model_config = ConfigDict(from_attributes=True)

    student_id: str
    name: str = "Learner"
    level: StudentLevel = StudentLevel.BEGINNER
    learning_style: LearningStyle = LearningStyle.READING_WRITING
    learning_speed: LearningSpeed = LearningSpeed.NORMAL
    preferred_difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    topics_learned: list[str] = Field(default_factory=list)
    weak_concepts: list[str] = Field(default_factory=list)
    quiz_scores: list[float] = Field(default_factory=list)


class ConceptScore(BaseModel):
    """Rolling proficiency of a single concept."""

    concept: str
    proficiency: float = Field(ge=0.0, le=1.0)
    attempts: int = 0


# --------------------------------------------------------------------------- #
# Lesson / explanation
# --------------------------------------------------------------------------- #
class Explanation(BaseModel):
    """The Teacher agent's output for a single concept."""

    topic: str
    summary: str
    explanation: str = Field(description="Simple-language explanation")
    examples: list[str] = Field(default_factory=list)
    analogies: list[str] = Field(default_factory=list)
    recap: str = Field(default="", description="One-paragraph recap")


class LessonPlan(BaseModel):
    """Planner output: the goal of the current tutoring run."""

    topic: str
    learning_goal: str
    level: StudentLevel
    prerequisites: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Quiz
# --------------------------------------------------------------------------- #
class QuizQuestion(BaseModel):
    """A single question inside a quiz."""

    id: str
    type: QuestionType
    topic: str
    question: str
    options: list[str] = Field(default_factory=list)  # MCQ only
    correct_answer: str
    explanation: str = ""
    points: int = 1


class Quiz(BaseModel):
    """A generated quiz. Composition: 5 MCQ + 2 numerical + 1 subjective."""

    id: str
    topic: str
    difficulty: DifficultyLevel
    questions: list[QuizQuestion] = Field(default_factory=list)

    @property
    def total_points(self) -> int:
        return sum(q.points for q in self.questions)


class AnswerSubmission(BaseModel):
    """One student answer to one question."""

    question_id: str
    answer: str


class QuizSubmission(BaseModel):
    """Full submission for a quiz."""

    quiz_id: str
    student_id: str
    answers: list[AnswerSubmission] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
class EvaluationResult(BaseModel):
    """Evaluation agent output for one quiz attempt."""

    score: float
    max_score: float
    percent: float = Field(ge=0.0, le=100.0)
    weak_concepts: list[str] = Field(default_factory=list)
    revision_topics: list[str] = Field(default_factory=list)
    next_lesson: str = ""
    feedback: str = ""


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #
class Recommendation(BaseModel):
    """Recommendation agent output."""

    next_topic: str
    rationale: str
    revision_schedule: list[str] = Field(default_factory=list)
    daily_plan: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    suggested_quiz_topics: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# RAG & Citations
# --------------------------------------------------------------------------- #
class RetrievedChunk(BaseModel):
    """A retrieved document fragment, with citation info and rich metadata."""

    content: str
    source: str
    page: int | None = None
    score: float = 0.0
    chunk_id: str | None = None
    document_id: str | None = None
    student_id: str | None = None
    document_title: str | None = None
    section_title: str | None = None
    section_path: str | None = None
    chunk_index: int | None = None
    content_hash: str | None = None
    dense_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    reranker_score: float | None = None
    relevance_score: float | None = None
    created_at: str | None = None


class Citation(BaseModel):
    """A source citation referencing an ingested document chunk."""

    document_id: str
    source: str
    page: int | None = None
    chunk_id: str | None = None
    section_title: str | None = None
    claim: str = ""
    cited_text: str = ""


class VerifiedCitation(BaseModel):
    """A verified citation with ownership, existence, and support checks."""

    citation: Citation
    is_valid: bool = True
    ownership_verified: bool = True
    page_verified: bool = True
    support_score: float = 1.0
    reason: str = ""


class CitationVerificationResult(BaseModel):
    """Overall outcome of the citation verification pipeline."""

    citations: list[VerifiedCitation] = Field(default_factory=list)
    all_valid: bool = True
    citation_correctness: float = 1.0
    citation_completeness: float = 1.0
    unsupported_claim_count: int = 0


class DecisionResult(BaseModel):
    """Normalized decision result across TypeSafe Jev and Gemini Decisions API."""

    decision_value: Any
    confidence: float = 1.0
    probabilities: dict[str, float] = Field(default_factory=dict)
    rubric_level: str | None = None
    provider: str
    model: str
    latency_ms: float = 0.0
    usage: dict[str, Any] = Field(default_factory=dict)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class RAGContext(BaseModel):
    """Everything the RAG agent passes to Teacher/Recommendation."""

    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    used: bool = False
    verification: CitationVerificationResult | None = None

    def as_pretty_string(self) -> str:
        """Flatten chunks into a single labelled string for prompt injection."""
        parts = []
        for i, chunk in enumerate(self.retrieved_chunks, start=1):
            loc = f" (p.{chunk.page})" if chunk.page is not None else ""
            sec = f" [{chunk.section_title}]" if chunk.section_title else ""
            parts.append(f"[{i}] Source: {chunk.source}{loc}{sec}\n{chunk.content}")
        return "\n\n".join(parts)


class DocumentRecord(BaseModel):
    """Metadata about an uploaded/processed document."""

    id: str
    student_id: str
    filename: str
    status: str
    chunk_count: int = 0
    content_hash: str | None = None
    created_at: str = ""


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #
class MemoryFact(BaseModel):
    """A single fact persisted to long-term memory."""

    fact_type: MemoryFactType
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class ProgressPoint(BaseModel):
    """A single point on the progress/time chart."""

    date: str
    score: float
    topic: str = ""


class DashboardSummary(BaseModel):
    """Aggregated payload for the dashboard home screen."""

    profile: StudentProfile
    topics_learned: list[str] = Field(default_factory=list)
    weak_concepts: list[str] = Field(default_factory=list)
    quiz_scores: list[float] = Field(default_factory=list)
    progress: list[ProgressPoint] = Field(default_factory=list)
    recommendations: Recommendation | None = None
    conversation_count: int = 0
    document_count: int = 0


# --------------------------------------------------------------------------- #
# Auth contracts
# --------------------------------------------------------------------------- #
class UserRegisterRequest(BaseModel):
    """Payload for POST /api/v1/auth/register."""

    student_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="Learner", min_length=1, max_length=128)


class UserLoginRequest(BaseModel):
    """Payload for POST /api/v1/auth/login."""

    student_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Response returned upon successful registration or authentication."""

    access_token: str
    token_type: str = "bearer"
    student: StudentProfile


# --------------------------------------------------------------------------- #
# Conversation Session contracts
# --------------------------------------------------------------------------- #
class ConversationSessionCreate(BaseModel):
    """Payload for creating a new named session."""

    title: str = Field(default="Tutoring Session", max_length=256)


class ConversationSessionView(BaseModel):
    """Public representation of a conversation thread."""

    id: str
    student_id: str
    title: str
    created_at: str
    updated_at: str


class ConversationMessageView(BaseModel):
    """Public representation of an individual message in a thread."""

    id: int
    student_id: str
    conversation_id: str
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: str


# --------------------------------------------------------------------------- #
# Memory contracts
# --------------------------------------------------------------------------- #
class EpisodicMemory(BaseModel):
    """A cross-session narrative memory item with optional similarity score."""

    id: int | str
    student_id: str
    session_id: str | None = None
    topic: str = ""
    summary: str
    event_type: str = "conversation_summary"
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    score: float | None = None


class Misconception(BaseModel):
    """A detected persistent conceptual error."""

    id: int | None = None
    student_id: str
    concept: str
    description: str
    severity: str = "medium"
    status: str = "active"
    confidence: float = 0.8
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    resolved_at: str | None = None


# --------------------------------------------------------------------------- #
# API contracts
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    """Body for POST /chat — one student turn in a tutoring conversation."""

    student_id: str
    message: str = Field(min_length=1, max_length=8000)
    topic: str | None = None
    with_quiz: bool = False
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Full result of a tutoring run (post-recommendation)."""

    student_id: str
    conversation_id: str = ""
    intent: str
    topic: str
    lesson: Explanation | None = None
    quiz: Quiz | None = None
    evaluation: EvaluationResult | None = None
    recommendations: Recommendation | None = None
    rag_sources: list[str] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
