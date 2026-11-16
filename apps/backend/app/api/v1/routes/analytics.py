"""Learning analytics and mastery evaluation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthorizationError
from app.schemas.domain import (
    ConceptMasterySchema,
    LearningAnalyticsSummary,
    RecommendationWithPrerequisites,
    StudentProfile,
)
from app.services.container import Container

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/progress", response_model=LearningAnalyticsSummary)
async def get_learning_progress(
    student_id: str | None = Query(None),
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> LearningAnalyticsSummary:
    """Retrieve comprehensive learning analytics distinguishing activity metrics from true concept mastery."""
    sid = student_id or current_student.student_id
    if sid != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot view another student's analytics")

    return container.analytics_service.get_student_summary(sid)


@router.get("/mastery", response_model=list[ConceptMasterySchema])
async def get_concept_mastery(
    student_id: str | None = Query(None),
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> list[ConceptMasterySchema]:
    """Retrieve fine-grained concept mastery states and confidence estimates."""
    sid = student_id or current_student.student_id
    if sid != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot view another student's mastery profile")

    return container.mastery_repo.list_mastery(sid)


@router.get("/recommendations", response_model=list[RecommendationWithPrerequisites])
async def get_prerequisite_recommendations(
    topic: str = Query("", description="Current topic under study"),
    limit: int = Query(5, ge=1, le=20),
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> list[RecommendationWithPrerequisites]:
    """Retrieve prioritized learning recommendations grounded in concept dependency DAG."""
    return container.prerequisite_engine.generate_recommendations(
        student_id=current_student.student_id,
        current_topic=topic,
        limit=limit,
    )
