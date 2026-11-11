"""Chat endpoints — tutoring conversation and quiz submission."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.schemas.domain import ChatRequest, ChatResponse, StudentProfile
from app.services.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _build_initial_state(
    req: ChatRequest,
    conversation_id: str,
    historical_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the LangGraph state for a tutoring turn with historical memory continuity."""
    return {
        "student_id": req.student_id,
        "conversation_id": conversation_id,
        "user_input": req.message,
        "topic": req.topic or None,
        "with_quiz": req.with_quiz,
        "intent": "general",
        "messages": historical_messages,
        "errors": [],
        "memory_updates": [],
        "lesson": None,
        "quiz": None,
        "evaluation": None,
        "recommendations": None,
        "rag_context": None,
        "rag_sources": [],
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> ChatResponse:
    """Send a message through the pre-compiled tutoring graph with session continuity."""
    if req.student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot initiate chat for another student")

    # 1. Manage Conversation Session
    if req.conversation_id:
        session = container.conversation_repo.get_session(req.conversation_id)
        if session is None:
            raise ResourceNotFoundError(f"Conversation session {req.conversation_id!r} not found")
        if session.student_id != current_student.student_id:
            raise AuthorizationError("Access denied: Conversation belongs to another student")
        conversation_id = req.conversation_id
    else:
        # Auto-create a session if not provided
        title = req.message[:40].strip() or "Tutoring Session"
        new_session = container.conversation_repo.create_session(
            student_id=current_student.student_id,
            title=title,
        )
        conversation_id = new_session.id

    # 2. Load recent conversational history to provide continuity across turns
    history_records = container.conversation_repo.list_messages(
        student_id=current_student.student_id,
        conversation_id=conversation_id,
        limit=10,
    )
    historical_messages = [
        {
            "role": h["role"],
            "content": h["content"],
            "persisted": True,
            "id": h["id"],
        }
        for h in history_records
    ]

    # 3. Invoke the pre-compiled graph singleton with thread isolation
    graph = container.tutoring_graph
    initial_state = _build_initial_state(req, conversation_id, historical_messages)
    config = {"configurable": {"thread_id": conversation_id}}

    try:
        final = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Tutoring graph execution failed: %s", exc, exc_info=True)
        raise

    return ChatResponse(
        student_id=req.student_id,
        conversation_id=conversation_id,
        intent=final.get("intent", "general"),
        topic=final.get("topic") or "",
        lesson=final.get("lesson"),
        quiz=final.get("quiz"),
        evaluation=final.get("evaluation"),
        recommendations=final.get("recommendations"),
        rag_sources=list(final.get("rag_sources") or []),
        messages=list(final.get("messages") or []),
    )


# ── POST /chat/submit-quiz ────────────────────────────────────────────────────


class SubmitQuizRequest(BaseModel):
    quiz_id: str
    student_id: str
    answers: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/chat/submit-quiz")
async def submit_quiz(
    req: SubmitQuizRequest,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict[str, Any]:
    """Submit quiz answers and receive evaluation results using pre-compiled evaluation graph."""
    if req.student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot submit quiz for another student")

    owner_id = container.quiz_repo.get_quiz_owner(req.quiz_id)
    if owner_id and owner_id != current_student.student_id:
        raise AuthorizationError("Access denied: Quiz belongs to another student")

    graph = container.evaluation_graph
    state: dict[str, Any] = {
        "student_id": req.student_id,
        "quiz_id": req.quiz_id,
        "answers": req.answers,
        "messages": [],
        "errors": [],
        "memory_updates": [],
    }
    config = {"configurable": {"thread_id": f"quiz_{req.quiz_id}"}}

    final = await graph.ainvoke(state, config=config)
    evaluation = final.get("evaluation")
    if evaluation is None:
        return {"error": "Evaluation could not be completed."}

    return {
        "evaluation": evaluation,
        "recommendations": final.get("recommendations"),
        "messages": list(final.get("messages") or []),
    }
