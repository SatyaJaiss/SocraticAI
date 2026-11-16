"""Dependency wiring — builds repos, LLM, RAG and the agent context.

The ``Container`` is constructed once per process and shared across the API and
the graph. Tests should construct their own with an in-memory database to avoid
touching the file system.
"""

from __future__ import annotations

from app.agents.context import AgentContext
from app.cache.manager import CacheManager
from app.context.builder import ContextBuilder
from app.core.config import Settings, get_settings
from app.db.connection import Database
from app.llm.clients.client import build_llm_client
from app.memory.manager import MemoryManager
from app.rag.citation.verifier import CitationVerifier
from app.rag.pipelines.service import RAGService
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    LessonRepository,
    MasteryRepository,
    MemoryRepository,
    ProgressRepository,
    QuizRepository,
    SocraticRepository,
    StudentRepository,
)
from app.routing.intent_router import JevIntentRouter
from app.tutoring import (
    AdaptiveExplanationEngine,
    AdaptiveQuizEngine,
    LearningAnalyticsService,
    MisconceptionDetector,
    PrerequisiteRecommendationEngine,
    SocraticEngine,
    StrategySelector,
)


class Container:
    """Process-wide singletons: database, repos, LLM, cache, memory, and RAG."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        database: Database | None = None,
        create_schema: bool = True,
    ) -> None:
        self.settings = settings or get_settings()

        if database is not None:
            self.db = database
        else:
            self.db = Database(self.settings.database)
            if create_schema and self.settings.database.create_on_startup:
                self.db.create_schema()

        self.student_repo = StudentRepository(self.db)
        self.quiz_repo = QuizRepository(self.db)
        self.conversation_repo = ConversationRepository(self.db)
        self.lesson_repo = LessonRepository(self.db)
        self.memory_repo = MemoryRepository(self.db)
        self.document_repo = DocumentRepository(self.db)
        self.progress_repo = ProgressRepository(self.db)
        self.mastery_repo = MasteryRepository(self.db, self.settings.mastery)
        self.socratic_repo = SocraticRepository(self.db)

        self.cache = CacheManager(self.settings.cache)
        self.llm = build_llm_client(self.settings.llm)
        self.rag = RAGService(
            self.settings.vector_store,
            cache_manager=self.cache,
            full_settings=self.settings,
        )
        self.citation_verifier = CitationVerifier(
            document_repo=self.document_repo,
            settings=self.settings.citation,
        )

        self.memory_manager = MemoryManager(
            db=self.db,
            memory_settings=self.settings.memory,
            vector_settings=self.settings.vector_store,
            llm=self.llm,
            cache_manager=self.cache,
        )
        self.context_builder = ContextBuilder(self.settings.context)
        self.router = JevIntentRouter(self.settings.routing)

        # Milestone 3: Educational Intelligence Services
        self.strategy_selector = StrategySelector()
        self.socratic_engine = SocraticEngine(
            self.socratic_repo,
            llm=self.llm,
            max_hint_level=self.settings.tutoring.max_hint_level,
        )
        self.explanation_engine = AdaptiveExplanationEngine(llm=self.llm)
        self.misconception_detector = MisconceptionDetector(
            self.memory_repo,
            student_repo=self.student_repo,
            settings=self.settings.misconception,
            llm=self.llm,
        )
        self.prerequisite_engine = PrerequisiteRecommendationEngine(
            self.mastery_repo,
            student_repo=self.student_repo,
            settings=self.settings.recommendation,
        )
        self.quiz_engine = AdaptiveQuizEngine(
            assessment_settings=self.settings.assessment,
            llm=self.llm,
        )
        self.analytics_service = LearningAnalyticsService(
            mastery_repo=self.mastery_repo,
            quiz_repo=self.quiz_repo,
            conversation_repo=self.conversation_repo,
            progress_repo=self.progress_repo,
            student_repo=self.student_repo,
            misconception_detector=self.misconception_detector,
        )

        try:
            self.mastery_repo.seed_default_curriculum()
        except Exception:
            pass

        self._tutoring_graph = None
        self._evaluation_graph = None

    @property
    def tutoring_graph(self):
        """Return the pre-compiled tutoring workflow graph singleton."""
        if self._tutoring_graph is None:
            from app.graphs.tutoring.workflow import build_tutoring_graph

            self._tutoring_graph = build_tutoring_graph(self.context())
        return self._tutoring_graph

    @property
    def evaluation_graph(self):
        """Return the pre-compiled quiz evaluation workflow graph singleton."""
        if self._evaluation_graph is None:
            from app.graphs.evaluation.workflow import build_evaluation_graph

            self._evaluation_graph = build_evaluation_graph(self.context())
        return self._evaluation_graph

    def context(self) -> AgentContext:
        """Return the :class:`AgentContext` handed to every agent node."""
        return AgentContext(
            llm=self.llm,
            settings=self.settings,
            student_repo=self.student_repo,
            quiz_repo=self.quiz_repo,
            conversation_repo=self.conversation_repo,
            lesson_repo=self.lesson_repo,
            memory_repo=self.memory_repo,
            document_repo=self.document_repo,
            progress_repo=self.progress_repo,
            mastery_repo=self.mastery_repo,
            socratic_repo=self.socratic_repo,
            rag=self.rag,
            cache=self.cache,
            memory_manager=self.memory_manager,
            context_builder=self.context_builder,
            router=self.router,
            citation_verifier=self.citation_verifier,
            strategy_selector=self.strategy_selector,
            socratic_engine=self.socratic_engine,
            explanation_engine=self.explanation_engine,
            misconception_detector=self.misconception_detector,
            prerequisite_engine=self.prerequisite_engine,
            quiz_engine=self.quiz_engine,
            analytics_service=self.analytics_service,
        )

    def dispose(self) -> None:
        """Release DB connection pools and cached graphs (called at shutdown / in tests)."""
        self._tutoring_graph = None
        self._evaluation_graph = None
        self.db.dispose()


_container_instance: Container | None = None


def get_container(settings: Settings | None = None) -> Container:
    """Return the process-wide :class:`Container` singleton."""
    global _container_instance  # noqa: PLW0603
    if _container_instance is None or settings is not None:
        _container_instance = Container(settings)
    return _container_instance
