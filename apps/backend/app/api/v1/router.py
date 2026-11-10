"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import chat, dashboard, documents, health, quizzes, students

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(students.router)
api_v1_router.include_router(quizzes.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(dashboard.router)

