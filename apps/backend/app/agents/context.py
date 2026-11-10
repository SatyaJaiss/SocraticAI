"""Shared dependency context injected into every agent node."""

from __future__ import annotations

from dataclasses import dataclass

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

