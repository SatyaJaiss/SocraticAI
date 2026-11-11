"""FastAPI dependency-injection helpers including authentication and container wiring."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.schemas.domain import StudentProfile

if TYPE_CHECKING:
    from app.agents.context import AgentContext
    from app.services.container import Container

# Auto-error is False so custom AuthenticationError is raised with proper formatting
http_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_container_cache() -> Container:
    """Lazy singleton used by all endpoint dependencies."""
    from app.services.container import get_container

    return get_container()


async def get_ctx() -> AgentContext:
    """Yield the shared AgentContext for graph-based endpoints."""
    return get_container_cache().context()


def get_container_dep() -> Container:
    """FastAPI dependency for endpoints that need the full container."""
    return get_container_cache()


async def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_scheme),
    container: Container = Depends(get_container_dep),
) -> StudentProfile:
    """Authenticate incoming HTTP request and extract the current student profile.

    Validates:
    1. Authorization Bearer header is present.
    2. JWT signature, algorithm, and expiration.
    3. Student identity exists in the database.

    Raises :class:`AuthenticationError` on any failure.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication token is missing. Please provide a Bearer token.")

    token = credentials.credentials
    secret_key = container.settings.auth.secret_key

    try:
        payload = decode_access_token(token, secret_key)
    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError(f"Failed to validate token: {exc}") from exc

    student_id = payload.get("sub")
    if not student_id:
        raise AuthenticationError("Token payload missing student identity ('sub')")

    profile = container.student_repo.get(student_id)
    if profile is None:
        raise AuthenticationError(f"Authenticated student {student_id!r} not found")

    return profile


async def get_optional_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_scheme),
    container: Container = Depends(get_container_dep),
) -> StudentProfile | None:
    """Extract authenticated student if credentials are provided, else None."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return await get_current_student(credentials, container)
    except AuthenticationError:
        return None
