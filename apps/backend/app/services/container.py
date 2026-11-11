"""Dependency wiring — builds repos, LLM, RAG and the agent context.

The ``Container`` is constructed once per process and shared across the API and
the graph. Tests should construct their own with an in-memory database to avoid
touching the file system.
"""

from __future__ import annotations

from app.agents.context import AgentContext
from app.core.config import Settings, get_settings
from app.db.connection import Database
from app.llm.clients.client import build_llm_client
from app.rag.pipelines.service import RAGService
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    LessonRepository,
    MemoryRepository,
    ProgressRepository,
    QuizRepository,
    StudentRepository,
)


class Container:
    """Process-wide singletons: database, repos, LLM and RAG."""

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

        self.llm = build_llm_client(self.settings.llm)
        self.rag = RAGService(self.settings.vector_store)

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
            rag=self.rag,
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
