"""Routing conditions and edge selectors for LangGraph workflows."""

from __future__ import annotations

from typing import Any

from app.core.config import Routes


def route_from_planner(state: dict[str, Any]) -> str:
    """Extract next agent chosen by the planner or default to END."""
    return state.get("next_agent", Routes.END)


def route_from_teacher(state: dict[str, Any], quiz_node: str, memory_node: str) -> str:
    """Route from teacher to quiz if with_quiz is requested, else memory."""
    return quiz_node if state.get("with_quiz") else memory_node

