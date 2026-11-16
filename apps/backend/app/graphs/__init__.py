"""LangGraph workflows and state machines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.graphs.states.state import EduAgentState, SocraticAIState

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from app.agents.context import AgentContext


def build_tutoring_graph(ctx: AgentContext) -> CompiledStateGraph:
    """Build and compile the tutoring workflow graph (lazy load to avoid circular deps)."""
    from app.graphs.tutoring.workflow import build_tutoring_graph as _build

    return _build(ctx)


def build_evaluation_graph(ctx: AgentContext) -> CompiledStateGraph:
    """Build and compile the evaluation workflow graph (lazy load to avoid circular deps)."""
    from app.graphs.evaluation.workflow import build_evaluation_graph as _build

    return _build(ctx)


__all__ = [
    "EduAgentState",
    "SocraticAIState",
    "build_evaluation_graph",
    "build_tutoring_graph",
]
