"""LangGraph workflow definition for the tutoring conversation (chat turn).

The graph coordinates:
    START -> router -> (greeting | small_talk | memory_query | progress | off_topic | clarification |
                        planner -> (teach | quiz | rag -> teach) -> memory -> recommendation) -> END
"""

from __future__ import annotations

import logging
from typing import Any

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
from app.graphs.routing.router import (
    route_from_entry,
    route_from_memory,
    route_from_planner,
    route_from_teacher,
)
from app.graphs.states.state import SocraticAIState

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """Specialized node handlers for tutoring graph."""

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx

    async def router(self, state: SocraticAIState) -> dict[str, Any]:
        """Classify user intent or dispatch pre-declared intents."""
        user_input = state.get("user_input", "")
        existing_intent = state.get("intent")

        # Preserve legacy explicit test intents
        if existing_intent in {"learn", "answer_question", "practice"}:
            return {"next_agent": "planner"}

        if self.ctx.router is not None and user_input:
            decision = await self.ctx.router.route(user_input)
            intent_val = decision.intent.value

            mapping = {
                "greeting": Routes.GREETING,
                "small_talk": Routes.SMALL_TALK,
                "off_topic": Routes.OFF_TOPIC,
                "unclear": Routes.CLARIFICATION,
                "learning_progress": Routes.PROGRESS,
                "memory_query": Routes.MEMORY_QUERY,
            }
            # Only intercept conversational fast paths; academic concepts route to planner
            if intent_val in mapping:
                return {
                    "intent": intent_val,
                    "intent_confidence": decision.confidence,
                    "intent_reasoning": decision.reasoning,
                    "routing_decision": decision.model_dump(),
                    "next_agent": mapping[intent_val],
                }

        return {"next_agent": "planner"}

    async def greeting(self, state: SocraticAIState) -> dict[str, Any]:
        """Lightweight greeting handler bypassing RAG and deep tutoring pipelines."""
        name = "there"
        student = self.ctx.student_repo.get(state.get("student_id", ""))
        if student and student.name:
            name = student.name
        greeting_text = (
            f"Hello {name}! I am SocraticAI, your personalized AI tutoring assistant. "
            "What topic, concept, or homework problem would you like to explore today?"
        )
        return {
            "messages": [{"role": "assistant", "content": greeting_text}],
            "next_agent": Routes.END,
            "intent": "greeting",
        }

    async def small_talk(self, _state: SocraticAIState) -> dict[str, Any]:
        """Lightweight polite small talk response handler."""
        reply_text = (
            "You're very welcome! I'm always here to help you understand tricky concepts, "
            "review notes, or practice with quiz questions. What should we tackle next?"
        )
        return {
            "messages": [{"role": "assistant", "content": reply_text}],
            "next_agent": Routes.END,
            "intent": "small_talk",
        }

    async def off_topic(self, _state: SocraticAIState) -> dict[str, Any]:
        """Polite redirection handler for off-topic requests."""
        redirect_text = (
            "I'm specifically focused on helping you learn academic concepts, review coursework, "
            "and practice problems. Could we return to your studies? What subject shall we work on?"
        )
        return {
            "messages": [{"role": "assistant", "content": redirect_text}],
            "next_agent": Routes.END,
            "intent": "off_topic",
        }

    async def clarification(self, _state: SocraticAIState) -> dict[str, Any]:
        """Clarification request node for ambiguous or unclear user input."""
        clarification_text = (
            "I didn't quite catch that. Could you please specify which topic, concept, or question "
            "you would like help with today?"
        )
        return {
            "messages": [{"role": "assistant", "content": clarification_text}],
            "next_agent": Routes.END,
            "intent": "unclear",
        }

    async def progress(self, state: SocraticAIState) -> dict[str, Any]:
        """Synthesize learning progress and analytics for the student."""
        student_id = state.get("student_id", "")
        student = self.ctx.student_repo.get(student_id)
        level = student.level if student else "beginner"
        scores = self.ctx.student_repo.list_concept_scores(student_id)
        topics = self.ctx.student_repo.list_topics(student_id)

        lines = ["Here is your learning progress overview:"]
        lines.append(f"• Current Level: {level.capitalize()}")
        lines.append(f"• Topics Studied: {len(topics)}")
        if scores:
            lines.append("• Concept Mastery Scores:")
            for s in scores[:5]:
                pct = round(s.proficiency * 100)
                lines.append(f"   - {s.concept}: {pct}% (Attempts: {s.attempts})")
        else:
            lines.append(
                "• No formal concept scores recorded yet. Complete a quiz to track your mastery!"
            )

        lines.append("\nKeep up the great work! What topic would you like to study next?")
        return {
            "messages": [{"role": "assistant", "content": "\n".join(lines)}],
            "next_agent": Routes.END,
            "intent": "learning_progress",
        }

    async def memory_query(self, state: SocraticAIState) -> dict[str, Any]:
        """Respond to inquiries regarding cross-session memory and learned history."""
        student_id = state.get("student_id", "")
        memories = []
        if self.ctx.memory_manager:
            query = state.get("user_input", "")
            res = self.ctx.memory_manager.retrieve_contextual_memories(student_id, query)
            memories = res.get("episodic_memories") or []

        lines = ["Here is what I remember from our prior tutoring sessions:"]
        if memories:
            for m in memories[:3]:
                lines.append(f"• [{m.topic or 'Study Session'}]: {m.summary}")
        else:
            lines.append(
                "• We don't have recorded memories from previous sessions yet. "
                "As we explore concepts together, I'll remember your key takeaways and milestones!"
            )
        lines.append("\nWhat would you like to explore today?")

        return {
            "messages": [{"role": "assistant", "content": "\n".join(lines)}],
            "next_agent": Routes.END,
            "intent": "memory_query",
        }

    async def socratic(self, state: SocraticAIState) -> dict[str, Any]:
        """Socratic dialogue and guided problem-solving handler."""
        student_id = state.get("student_id", "")
        conversation_id = state.get("conversation_id", "")
        user_input = state.get("user_input", "")
        topic = state.get("topic") or "General Problem Solving"

        if (
            getattr(self.ctx, "socratic_engine", None) is not None
            and getattr(self.ctx, "socratic_repo", None) is not None
        ):
            active = self.ctx.socratic_repo.get_active_session(student_id, conversation_id)
            if active:
                res = self.ctx.socratic_engine.process_student_turn(active.id, user_input)
            else:
                res = self.ctx.socratic_engine.start_session(
                    student_id=student_id,
                    conversation_id=conversation_id,
                    concept=topic,
                    problem_statement=user_input,
                    total_steps=3,
                )
            msg_content = f"{res.feedback}\n\n{res.question}" if res.question else res.feedback
            if res.hint:
                msg_content += f"\n\nHint (Level {res.hint_level}): {res.hint}"

            return {
                "socratic_response": res.model_dump(),
                "messages": [{"role": "assistant", "content": msg_content}],
                "next_agent": Routes.END,
                "intent": "practice",
            }

        return {
            "messages": [
                {"role": "assistant", "content": "Let's explore this problem step by step."}
            ],
            "next_agent": Routes.END,
        }


# --------------------------------------------------------------------------- #
# Main Graph Builder
# --------------------------------------------------------------------------- #
def build_tutoring_graph(ctx: AgentContext) -> CompiledStateGraph:
    """Build and compile the main tutoring workflow graph."""
    planner = PlannerAgent(ctx)
    rag = RAGAgent(ctx)
    teacher = TeacherAgent(ctx)
    quiz = QuizAgent(ctx)
    memory = MemoryAgent(ctx)
    recommendation = RecommendationAgent(ctx)

    nodes = WorkflowNodes(ctx)
    graph = StateGraph(SocraticAIState)

    # --- fast-path & router nodes ---
    graph.add_node("router", nodes.router)
    graph.add_node("greeting", nodes.greeting)
    graph.add_node("small_talk", nodes.small_talk)
    graph.add_node("off_topic", nodes.off_topic)
    graph.add_node("clarification", nodes.clarification)
    graph.add_node("progress", nodes.progress)
    graph.add_node("memory_query", nodes.memory_query)
    graph.add_node("socratic", nodes.socratic)

    # --- core agent nodes ---
    graph.add_node(planner.name, planner.run)
    graph.add_node(rag.name, rag.run)
    graph.add_node(teacher.name, teacher.run)
    graph.add_node(quiz.name, quiz.run)
    graph.add_node(memory.name, memory.run)
    graph.add_node(recommendation.name, recommendation.run)

    # --- entry edge ---
    graph.add_edge(START, "router")

    # --- conditional edge from router ---
    graph.add_conditional_edges(
        "router",
        route_from_entry,
        {
            Routes.GREETING: "greeting",
            Routes.SMALL_TALK: "small_talk",
            Routes.OFF_TOPIC: "off_topic",
            Routes.CLARIFICATION: "clarification",
            Routes.PROGRESS: "progress",
            Routes.MEMORY_QUERY: "memory_query",
            "planner": planner.name,
        },
    )

    # --- fast paths converge to memory for transcript persistence ---
    graph.add_edge("greeting", memory.name)
    graph.add_edge("small_talk", memory.name)
    graph.add_edge("off_topic", memory.name)
    graph.add_edge("clarification", memory.name)
    graph.add_edge("progress", memory.name)
    graph.add_edge("memory_query", memory.name)

    # --- planner -> conditional routing ---
    graph.add_conditional_edges(
        planner.name,
        route_from_planner,
        {
            Routes.TEACH: teacher.name,
            Routes.ANSWER_QUESTION: rag.name,
            Routes.QUIZ: quiz.name,
            Routes.SOCRATIC: "socratic",
            Routes.END: END,
        },
    )

    # --- socratic -> memory ---
    graph.add_edge("socratic", memory.name)

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

    # --- quiz -> memory ---
    graph.add_edge(quiz.name, memory.name)

    # --- memory -> conditional: END for fast-paths, else recommendation ---
    graph.add_conditional_edges(
        memory.name,
        lambda state: route_from_memory(state, recommendation.name),
        {
            recommendation.name: recommendation.name,
            Routes.END: END,
        },
    )

    # --- recommendation -> END ---
    graph.add_edge(recommendation.name, END)

    logger.debug("Tutoring graph compiled with intelligent routing and fast-path handlers")
    return graph.compile()
