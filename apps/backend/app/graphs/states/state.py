"""LangGraph state definition for the SocraticAI tutoring workflow.

Design rationale
----------------
LangGraph threads a single state object through every node. We model it as a
``TypedDict`` so each node (agent) can declare exactly which keys it reads and
which partial updates it writes back. Fields that must *accumulate* across
steps (``messages``, ``memory_updates``) use ``Annotated[list, operator.add]``
so multiple agents can append without clobbering each other.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SocraticAIState(TypedDict, total=False):
    """Shared state threaded through the tutoring graph."""

    # --- Turn context --------------------------------------------------------
    student_id: str
    conversation_id: str
    user_input: str
    topic: str | None
    with_quiz: bool

    # --- Routing & Intent ----------------------------------------------------
    intent: str  # IntentType or legacy ChatIntent value
    intent_confidence: float
    intent_reasoning: str
    routing_decision: dict[str, Any]
    learning_goal: str
    level: str  # models.enums.StudentLevel value

    # --- Context & Layered Memory --------------------------------------------
    episodic_memories: list[dict[str, Any]]
    semantic_profile: dict[str, Any]
    assembled_prompt: str
    token_counts: dict[str, int]

    # --- Teacher -------------------------------------------------------------
    lesson: dict[str, Any]  # serialised models.schemas.Explanation

    # --- Quiz / evaluation ----------------------------------------------------
    quiz: dict[str, Any]  # serialised models.schemas.Quiz
    quiz_id: str | None  # id of the quiz being answered
    answers: list[dict[str, Any]]  # serialised AnswerSubmission list
    evaluation: dict[str, Any]  # serialised EvaluationResult

    # --- Memory / recommendation ----------------------------------------------
    memory_updates: Annotated[list[dict[str, Any]], operator.add]
    recommendations: dict[str, Any]  # serialised Recommendation

    # --- RAG & Citations -----------------------------------------------------
    rag_context: dict[str, Any]  # serialised RAGContext
    rag_sources: list[str]
    citation_verification: dict[str, Any]

    # --- Conversation transcript (accumulating) --------------------------------
    messages: Annotated[list[dict[str, Any]], operator.add]

    # --- Housekeeping ----------------------------------------------------------
    errors: Annotated[list[str], operator.add]
    next_agent: str


# Backward-compatibility alias
EduAgentState = SocraticAIState
