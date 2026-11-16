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
from app.repositories.memory_repository import MemoryRepository
from app.repositories.progress_repository import ProgressRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.student_repository import StudentRepository

if TYPE_CHECKING:
    from app.cache.manager import CacheManager
    from app.context.builder import ContextBuilder
    from app.memory.manager import MemoryManager
    from app.rag.citation.verifier import CitationVerifier
    from app.routing.intent_router import JevIntentRouter


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
