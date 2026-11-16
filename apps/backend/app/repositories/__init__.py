"""Data-access repositories, one file per aggregate root."""

from app.repositories.base_repository import BaseRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.lesson_repository import LessonRepository
from app.repositories.mastery_repository import MasteryRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.progress_repository import ProgressRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.socratic_repository import SocraticRepository
from app.repositories.student_repository import StudentRepository

__all__ = [
    "BaseRepository",
    "ConversationRepository",
    "DocumentRepository",
    "LessonRepository",
    "MasteryRepository",
    "MemoryRepository",
    "ProgressRepository",
    "QuizRepository",
    "SocraticRepository",
    "StudentRepository",
]
