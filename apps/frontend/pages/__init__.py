"""Frontend page views."""

from __future__ import annotations

from apps.frontend.pages.chat import render_chat
from apps.frontend.pages.dashboard import render_dashboard
from apps.frontend.pages.documents import render_documents
from apps.frontend.pages.quiz import render_quiz

__all__ = [
    "render_chat",
    "render_dashboard",
    "render_documents",
    "render_quiz",
]

