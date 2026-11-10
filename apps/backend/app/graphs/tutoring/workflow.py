"""LangGraph workflow definition for the tutoring conversation (chat turn).

The graph coordinates:
    planner -> (teach | quiz | rag -> teach) -> memory -> recommendation
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.context import AgentContext
from app.agents.memory.agent import MemoryAgent
from app.agents.planner.agent import PlannerAgent
from app.agents.quiz.agent import QuizAgent
from app.agents.rag.agent import RAGAgent
from app.agents.recommendation.agent import RecommendationAgent
from app.agents.teacher.agent import TeacherAgent
from app.core.config import Routes
from app.graphs.routing.router import route_from_planner, route_from_teacher
from app.graphs.states.state import SocraticAIState

logger = logging.getLogger(__name__)


def build_tutoring_graph(ctx: AgentContext) -> CompiledStateGraph:
    """Build and compile the main tutoring workflow graph."""
    planner = PlannerAgent(ctx)
    rag = RAGAgent(ctx)
    teacher = TeacherAgent(ctx)
    quiz = QuizAgent(ctx)
    memory = MemoryAgent(ctx)
    recommendation = RecommendationAgent(ctx)

    graph = StateGraph(SocraticAIState)

    # --- nodes ---
    graph.add_node(planner.name, planner.run)
    graph.add_node(rag.name, rag.run)
    graph.add_node(teacher.name, teacher.run)
    graph.add_node(quiz.name, quiz.run)
    graph.add_node(memory.name, memory.run)
    graph.add_node(recommendation.name, recommendation.run)

    # --- start -> planner ---
    graph.add_edge(START, planner.name)

    # --- planner -> conditional routing ---
    graph.add_conditional_edges(
        planner.name,
        route_from_planner,
        {
            Routes.TEACH: teacher.name,
            Routes.ANSWER_QUESTION: rag.name,
            Routes.QUIZ: quiz.name,
            Routes.END: END,
        },
    )

    # --- rag -> teacher (answer grounded in retrieved notes) ---
    graph.add_edge(rag.name, teacher.name)

    # --- teacher -> optional quiz, else memory ---
    graph.add_conditional_edges(
        teacher.name,
        lambda state: route_from_teacher(state, quiz.name, memory.name),
        {
            quiz.name: quiz.name,
            memory.name: memory.name,
        },
    )

    # --- quiz / memory / recommendation tail ---
    graph.add_edge(quiz.name, memory.name)
    graph.add_edge(memory.name, recommendation.name)
    graph.add_edge(recommendation.name, END)

    logger.debug("Tutoring graph compiled")
    return graph.compile()

