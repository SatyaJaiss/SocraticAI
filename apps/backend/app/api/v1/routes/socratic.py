"""Interactive Socratic problem-solving and progressive hint endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.schemas.domain import SocraticTurnResponse, StudentProfile
from app.services.container import Container

router = APIRouter(prefix="/api/v1/socratic", tags=["socratic"])


class StartSocraticRequest(BaseModel):
    """Request payload to initiate a guided problem-solving session."""

    concept: str = Field(min_length=1, max_length=256)
    problem_statement: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    total_steps: int = Field(3, ge=1, le=10)
    target_solution: str = ""


class SocraticRespondRequest(BaseModel):
    """Student step attempt response."""

    session_id: str
    response: str = Field(min_length=1, max_length=4000)


class SocraticHintRequest(BaseModel):
    """Progressive hint request."""

    session_id: str


@router.post("/start", response_model=SocraticTurnResponse)
async def start_socratic_session(
    payload: StartSocraticRequest,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> SocraticTurnResponse:
    """Initialize a guided Socratic dialogue session and formulate the first step question."""
    # PII sanitization and input rails
    redacted_prob, pii_ctx, _ = container.pii_service.redact_user_input(
        payload.problem_statement, student_id=current_student.student_id
    )
    input_check = container.guardrails_service.validate_input(redacted_prob)
    if not input_check.allowed:
        return SocraticTurnResponse(
            session_id="blocked",
            concept=payload.concept,
            current_step=0,
            total_steps=payload.total_steps,
            question=input_check.reason or "Request blocked by safety rails.",
            hint_level=0,
            is_stuck=False,
            is_completed=False,
        )

    cid = payload.conversation_id or "default"
    resp = container.socratic_engine.start_session(
        student_id=current_student.student_id,
        conversation_id=cid,
        concept=payload.concept,
        problem_statement=redacted_prob,
        target_solution=payload.target_solution,
        total_steps=payload.total_steps,
    )
    resp.question = container.pii_service.restore_response(resp.question, pii_ctx)
    pii_ctx.clear()
    return resp


@router.post("/respond", response_model=SocraticTurnResponse)
async def respond_to_socratic_step(
    payload: SocraticRespondRequest,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> SocraticTurnResponse:
    """Submit reasoning or answer for the active Socratic step."""
    session = container.socratic_repo.get_session(payload.session_id)
    if not session:
        raise ResourceNotFoundError(f"Socratic session {payload.session_id} not found")
    if session.student_id != current_student.student_id:
        raise AuthorizationError(
            "Access denied: You cannot participate in another student's session"
        )

    # PII sanitization and input rails
    redacted_resp, pii_ctx, _ = container.pii_service.redact_user_input(
        payload.response, student_id=current_student.student_id
    )
    input_check = container.guardrails_service.validate_input(redacted_resp)
    if not input_check.allowed:
        return SocraticTurnResponse(
            session_id=payload.session_id,
            concept=session.concept,
            current_step=session.current_step,
            total_steps=session.total_steps,
            question=input_check.reason or "Request blocked by safety rails.",
            hint_level=session.hint_level,
            is_stuck=False,
            is_completed=False,
        )

    resp = container.socratic_engine.process_student_turn(
        session_id=payload.session_id,
        student_input=redacted_resp,
    )
    if resp.question:
        resp.question = container.pii_service.restore_response(resp.question, pii_ctx)
    if resp.hint:
        resp.hint = container.pii_service.restore_response(resp.hint, pii_ctx)
    if resp.feedback:
        resp.feedback = container.pii_service.restore_response(resp.feedback, pii_ctx)
    pii_ctx.clear()
    return resp


@router.post("/hint", response_model=SocraticTurnResponse)
async def get_progressive_hint(
    payload: SocraticHintRequest,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> SocraticTurnResponse:
    """Escalate to the next bounded hint level without revealing full answers prematurely."""
    session = container.socratic_repo.get_session(payload.session_id)
    if not session:
        raise ResourceNotFoundError(f"Socratic session {payload.session_id} not found")
    if session.student_id != current_student.student_id:
        raise AuthorizationError(
            "Access denied: You cannot request hints for another student's session"
        )

    return container.socratic_engine.escalate_hint(
        session_id=payload.session_id,
        reason="Student requested hint",
    )
