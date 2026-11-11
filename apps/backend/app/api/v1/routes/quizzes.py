"""Quiz endpoints — list quizzes and view individual quizzes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.schemas.domain import StudentProfile
from app.services.container import Container

router = APIRouter(prefix="/api/v1", tags=["quizzes"])


@router.get("/quizzes/{student_id}")
async def list_quizzes(
    student_id: str,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict:
    """List quiz ids for a student, newest first."""
    if student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot list another student's quizzes")
    quiz_ids = container.quiz_repo.list_quizzes(student_id)
    return {"student_id": student_id, "quiz_ids": quiz_ids}


@router.get("/quiz/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict:
    """Get a specific quiz (with questions) by ID."""
    owner_id = container.quiz_repo.get_quiz_owner(quiz_id)
    if owner_id is None:
        raise ResourceNotFoundError(f"Quiz {quiz_id!r} not found")

    if owner_id != current_student.student_id:
        raise AuthorizationError("Access denied: Quiz belongs to another student")

    quiz = container.quiz_repo.get_quiz(quiz_id)
    if quiz is None:
        raise ResourceNotFoundError(f"Quiz {quiz_id!r} not found")
    return quiz.model_dump()
