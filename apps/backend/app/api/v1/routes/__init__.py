"""API v1 route modules."""

from __future__ import annotations

from app.api.v1.routes import chat, dashboard, documents, health, quizzes, students

__all__ = [
    "chat",
    "dashboard",
    "documents",
    "health",
    "quizzes",
    "students",
]
