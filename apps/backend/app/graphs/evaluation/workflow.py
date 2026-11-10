"""LangGraph workflow definition for the quiz-evaluation workflow.

The graph coordinates:
    evaluation -> memory -> recommendation -> END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.context import AgentContext
from app.agents.evaluation.agent import EvaluationAgent
from app.agents.memory.agent import MemoryAgent
from app.agents.recommendation.agent import RecommendationAgent
from app.graphs.states.state import SocraticAIState

logger = logging.getLogger(__name__)


def build_evaluation_graph(ctx: AgentContext) -> CompiledStateGraph:
    """Build and compile the quiz-evaluation workflow graph."""
    evaluation = EvaluationAgent(ctx)
    memory = MemoryAgent(ctx)
    recommendation = RecommendationAgent(ctx)

    graph = StateGraph(SocraticAIState)

    graph.add_node(evaluation.name, evaluation.run)
    graph.add_node(memory.name, memory.run)
    graph.add_node(recommendation.name, recommendation.run)

    graph.add_edge(START, evaluation.name)
    graph.add_edge(evaluation.name, memory.name)
    graph.add_edge(memory.name, recommendation.name)
    graph.add_edge(recommendation.name, END)

    logger.debug("Evaluation graph compiled")
    return graph.compile()

