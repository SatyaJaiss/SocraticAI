"""Core configuration, logging, exceptions, and dependency management."""

from __future__ import annotations

from app.core.config import Routes, Settings, get_settings
from app.core.dependencies import get_container_dep, get_ctx
from app.core.exceptions import (
    EduAgentError,
    SocraticAIError,
    register_exception_handlers,
)
from app.core.logging import get_logger, setup_logging

__all__ = [
    "EduAgentError",
    "Routes",
    "Settings",
    "SocraticAIError",
    "get_container_dep",
    "get_ctx",
    "get_logger",
    "get_settings",
    "register_exception_handlers",
    "setup_logging",
]

