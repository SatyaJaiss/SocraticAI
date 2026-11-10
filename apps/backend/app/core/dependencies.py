"""FastAPI dependency-injection helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.context import AgentContext
    from app.services.container import Container


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

