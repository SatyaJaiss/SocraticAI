"""Frontend client services."""

from __future__ import annotations

from apps.frontend.services.api_client import (
    EduAgentClient,
    EduAgentClientError,
    SocraticAIClient,
    SocraticAIClientError,
)

__all__ = [
    "EduAgentClient",
    "EduAgentClientError",
    "SocraticAIClient",
    "SocraticAIClientError",
]

