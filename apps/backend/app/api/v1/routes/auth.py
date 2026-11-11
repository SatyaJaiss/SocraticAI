"""Authentication endpoints for student registration, login, and identity verification."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token
from app.schemas.domain import (
    StudentProfile,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    req: UserRegisterRequest,
    container: Container = Depends(get_container_dep),
) -> TokenResponse:
    """Register a new student account with a hashed password and issue an access token."""
    profile = container.student_repo.register(
        student_id=req.student_id,
        password=req.password,
        name=req.name,
    )
    expires_delta = container.settings.auth.access_token_expire_minutes * 60
    token = create_access_token(
        subject=profile.student_id,
        secret_key=container.settings.auth.secret_key,
        expires_delta_seconds=expires_delta,
    )
    logger.info("Registered new student account: %s", profile.student_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        student=profile,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: UserLoginRequest,
    container: Container = Depends(get_container_dep),
) -> TokenResponse:
    """Authenticate student credentials and return a signed JWT access token."""
    profile = container.student_repo.authenticate(
        student_id=req.student_id,
        password=req.password,
    )
    if profile is None:
        raise AuthenticationError("Invalid student ID or password")

    expires_delta = container.settings.auth.access_token_expire_minutes * 60
    token = create_access_token(
        subject=profile.student_id,
        secret_key=container.settings.auth.secret_key,
        expires_delta_seconds=expires_delta,
    )
    logger.info("Student authenticated: %s", profile.student_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        student=profile,
    )


@router.get("/me", response_model=StudentProfile)
async def get_me(
    current_student: StudentProfile = Depends(get_current_student),
) -> StudentProfile:
    """Return the profile of the currently authenticated student."""
    return current_student

