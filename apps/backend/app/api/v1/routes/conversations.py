"""Conversation and session management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.schemas.domain import (
    ConversationMessageView,
    ConversationSessionCreate,
    ConversationSessionView,
    StudentProfile,
)
from app.services.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("", response_model=ConversationSessionView, status_code=201)
async def create_conversation(
    req: ConversationSessionCreate,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> ConversationSessionView:
    """Create a new independent conversation session for the authenticated student."""
    session = container.conversation_repo.create_session(
        student_id=current_student.student_id,
        title=req.title,
    )
    logger.info("Created conversation %s for student %s", session.id, current_student.student_id)
    return session


@router.get("", response_model=list[ConversationSessionView])
async def list_conversations(
    limit: int = 50,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> list[ConversationSessionView]:
    """List conversation sessions belonging to the authenticated student."""
    return container.conversation_repo.list_sessions(
        student_id=current_student.student_id,
        limit=limit,
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageView])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> list[ConversationMessageView]:
    """Retrieve message history for a specific conversation session."""
    session = container.conversation_repo.get_session(conversation_id)
    if session is None:
        raise ResourceNotFoundError(f"Conversation {conversation_id!r} not found")

    if session.student_id != current_student.student_id:
        raise AuthorizationError("Access denied: Conversation belongs to another student")

    messages = container.conversation_repo.list_messages(
        student_id=current_student.student_id,
        conversation_id=conversation_id,
        limit=limit,
    )
    return [
        ConversationMessageView(
            id=m["id"],
            student_id=m["student_id"],
            conversation_id=m.get("conversation_id", conversation_id),
            role=m["role"],
            content=m["content"],
            metadata=m.get("metadata", {}),
            created_at=m["created_at"],
        )
        for m in messages
    ]


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict[str, str]:
    """Delete a conversation session and all its messages."""
    session = container.conversation_repo.get_session(conversation_id)
    if session is None:
        raise ResourceNotFoundError(f"Conversation {conversation_id!r} not found")

    if session.student_id != current_student.student_id:
        raise AuthorizationError("Access denied: Conversation belongs to another student")

    success = container.conversation_repo.delete_session(
        student_id=current_student.student_id,
        conversation_id=conversation_id,
    )
    if not success:
        raise ResourceNotFoundError(f"Conversation {conversation_id!r} could not be deleted")

    return {"status": "deleted", "conversation_id": conversation_id}

