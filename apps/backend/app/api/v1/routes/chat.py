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
    *,
    episodic_memories: list[dict[str, Any]] | None = None,
    semantic_profile: dict[str, Any] | None = None,
    assembled_prompt: str = "",
    token_counts: dict[str, int] | None = None,
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
        "episodic_memories": episodic_memories or [],
        "semantic_profile": semantic_profile or {},
        "assembled_prompt": assembled_prompt,
        "token_counts": token_counts or {},
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

    # 1.1 Mandatory PII Redaction Boundary: sanitize input before ANY model/memory processing
    redacted_message, pii_ctx, _ = container.pii_service.redact_user_input(
        req.message, student_id=current_student.student_id
    )

    # 1.2 NVIDIA NeMo Input Guardrail Validation
    input_check = container.guardrails_service.validate_input(redacted_message)
    if not input_check.allowed:
        refusal = (
            input_check.reason or "I cannot process this request as it violates safety guidelines."
        )
        return ChatResponse(
            student_id=req.student_id,
            conversation_id=conversation_id,
            intent="blocked_by_guardrails",
            topic="",
            lesson=None,
            messages=[{"role": "assistant", "content": refusal}],
        )

    # 2. Load recent conversational history using configured token/turn budget
    history_limit = container.settings.conversation.history_limit
    history_records = container.conversation_repo.list_messages(
        student_id=current_student.student_id,
        conversation_id=conversation_id,
        limit=history_limit,
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

    # 3. Retrieve layered cross-session memories and assemble token-budgeted prompt
    contextual_data = container.memory_manager.retrieve_contextual_memories(
        student_id=current_student.student_id,
        query=redacted_message,
    )
    raw_memories = contextual_data.get("episodic_memories") or []
    semantic_profile = contextual_data.get("semantic_profile") or {}

    assembled = container.context_builder.build_context(
        user_message=redacted_message,
        history_messages=historical_messages,
        episodic_memories=raw_memories,
        semantic_profile=semantic_profile,
    )

    episodic_memories = [m.model_dump() for m in raw_memories]

    # 4. Invoke the pre-compiled graph singleton with thread isolation
    graph = container.tutoring_graph
    initial_state = _build_initial_state(
        req,
        conversation_id,
        assembled.history_messages,
        episodic_memories=episodic_memories,
        semantic_profile=semantic_profile,
        assembled_prompt=assembled.assembled_prompt,
        token_counts=assembled.token_counts,
    )
    # Ensure state carries the sanitized input
    initial_state["user_input"] = redacted_message
    config = {"configurable": {"thread_id": conversation_id}}

    try:
        final = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Tutoring graph execution failed: %s", exc, exc_info=True)
        raise

    # 5. Output Rails Validation & Controlled Safe PII Restoration
    raw_lesson = final.get("lesson")
    if raw_lesson is not None:
        if hasattr(raw_lesson, "explanation"):
            out_check = container.guardrails_service.validate_output(raw_lesson.explanation)
            if not out_check.allowed:
                raw_lesson.explanation = (
                    "I apologize, but this response was withheld by content safety policies."
                )
            raw_lesson.explanation = container.pii_service.restore_response(
                raw_lesson.explanation, pii_ctx
            )
        elif isinstance(raw_lesson, dict) and "explanation" in raw_lesson:
            content = raw_lesson.get("explanation", "")
            out_check = container.guardrails_service.validate_output(content)
            if not out_check.allowed:
                content = "I apologize, but this response was withheld by content safety policies."
            raw_lesson["explanation"] = container.pii_service.restore_response(content, pii_ctx)
        final["lesson"] = raw_lesson

    final_messages = list(final.get("messages") or [])
    for msg in final_messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
            content = msg["content"]
            out_check = container.guardrails_service.validate_output(content)
            if not out_check.allowed:
                content = "I apologize, but this response was withheld by content safety policies."
            msg["content"] = container.pii_service.restore_response(content, pii_ctx)

    pii_ctx.clear()

    # 6. Periodic cross-session consolidation trigger
    summary_trigger = container.settings.conversation.summary_trigger_turns
    if len(history_records) > 0 and len(history_records) % summary_trigger == 0:
        try:
            await container.memory_manager.consolidate_session(
                student_id=current_student.student_id,
                session_id=conversation_id,
                messages=historical_messages,
                topic=req.topic or final.get("topic") or "",
            )
        except Exception as exc:
            logger.warning("Session memory consolidation failed: %s", exc)

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
