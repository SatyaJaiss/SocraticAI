"""API v1 route modules."""

from __future__ import annotations

from app.api.v1.routes import (
    auth,
    chat,
    conversations,
    dashboard,
    documents,
    health,
    quizzes,
    students,
)

__all__ = [
    "auth",
    "chat",
    "conversations",
    "dashboard",
    "documents",
    "health",
    "quizzes",
    "students",
]
