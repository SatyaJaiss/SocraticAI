"""Shared dependency context injected into every agent node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.llm.clients.client import LLMClient
from app.rag.pipelines.service import RAGService
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.lesson_repository import LessonRepository
from app.repositories.mastery_repository import MasteryRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.progress_repository import ProgressRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.socratic_repository import SocraticRepository
from app.repositories.student_repository import StudentRepository

if TYPE_CHECKING:
    from app.cache.manager import CacheManager
    from app.context.builder import ContextBuilder
    from app.memory.manager import MemoryManager
    from app.rag.citation.verifier import CitationVerifier
    from app.routing.intent_router import JevIntentRouter
    from app.tutoring.analytics_service import LearningAnalyticsService
    from app.tutoring.explanation_engine import AdaptiveExplanationEngine
    from app.tutoring.misconception_detector import MisconceptionDetector
    from app.tutoring.quiz_engine import AdaptiveQuizEngine
    from app.tutoring.recommendation_engine import PrerequisiteRecommendationEngine
    from app.tutoring.socratic_engine import SocraticEngine
    from app.tutoring.strategy_selector import StrategySelector


@dataclass
class AgentContext:
    """Everything an agent needs: LLM, RAG and repositories."""

    llm: LLMClient
    settings: Settings
    student_repo: StudentRepository
    quiz_repo: QuizRepository
    conversation_repo: ConversationRepository
    lesson_repo: LessonRepository
    memory_repo: MemoryRepository
    document_repo: DocumentRepository
    progress_repo: ProgressRepository
    rag: RAGService
    cache: CacheManager | None = None
    memory_manager: MemoryManager | None = None
    context_builder: ContextBuilder | None = None
    router: JevIntentRouter | None = None
    citation_verifier: CitationVerifier | None = None
    mastery_repo: MasteryRepository | None = None
    socratic_repo: SocraticRepository | None = None
    strategy_selector: StrategySelector | None = None
    socratic_engine: SocraticEngine | None = None
    explanation_engine: AdaptiveExplanationEngine | None = None
    misconception_detector: MisconceptionDetector | None = None
    prerequisite_engine: PrerequisiteRecommendationEngine | None = None
    quiz_engine: AdaptiveQuizEngine | None = None
    analytics_service: LearningAnalyticsService | None = None
