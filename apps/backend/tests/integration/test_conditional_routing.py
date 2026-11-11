"""Integration tests for conditional LangGraph workflow routing and fast-path execution."""

from __future__ import annotations

import pytest
from app.graphs.tutoring.workflow import build_tutoring_graph


class TestConditionalRouting:
    @pytest.mark.asyncio
    async def test_greeting_fast_path(self, ctx):
        ctx.student_repo.get_or_create("s_greeting", name="Ada")
        graph = build_tutoring_graph(ctx)

        state = {
            "student_id": "s_greeting",
            "user_input": "Hello there! Good morning.",
            "messages": [],
            "conversation_id": "conv_greeting_1",
        }

        final = await graph.ainvoke(state)

        # Fast-path verification: no lesson or quiz generated
        assert final["intent"] == "greeting"
        assert final.get("lesson") is None
        assert final.get("quiz") is None
        assert final.get("recommendations") is None

        # Friendly greeting message produced
        assistant_msgs = [m for m in final["messages"] if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "Hello Ada" in assistant_msgs[-1]["content"]

        # Transcript was persisted in conversation repository
        stored = ctx.conversation_repo.list_messages("s_greeting", "conv_greeting_1")
        assert len(stored) >= 1

    @pytest.mark.asyncio
    async def test_small_talk_fast_path(self, ctx):
        ctx.student_repo.get_or_create("s_smalltalk")
        graph = build_tutoring_graph(ctx)

        state = {
            "student_id": "s_smalltalk",
            "user_input": "Thank you so much for the help!",
            "messages": [],
            "conversation_id": "conv_smalltalk_1",
        }

        final = await graph.ainvoke(state)
        assert final["intent"] == "small_talk"
        assert final.get("lesson") is None

        assistant_msgs = [m for m in final["messages"] if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "welcome" in assistant_msgs[-1]["content"].lower()

    @pytest.mark.asyncio
    async def test_memory_query_fast_path(self, ctx):
        ctx.student_repo.get_or_create("s_mem")
        # Add a prior memory
        if ctx.memory_manager:
            ctx.memory_manager.episodic.add_memory(
                "s_mem",
                topic="Newton's Laws",
                summary="Discussed F=ma and action-reaction pairs.",
            )

        graph = build_tutoring_graph(ctx)
        state = {
            "student_id": "s_mem",
            "user_input": "What did we discuss in our last session?",
            "messages": [],
            "conversation_id": "conv_mem_1",
        }

        final = await graph.ainvoke(state)
        assert final["intent"] == "memory_query"
        assert final.get("lesson") is None

        assistant_msgs = [m for m in final["messages"] if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "remember" in assistant_msgs[-1]["content"].lower()

    @pytest.mark.asyncio
    async def test_learning_progress_fast_path(self, ctx):
        ctx.student_repo.get_or_create("s_prog")
        ctx.student_repo.upsert_concept_score("s_prog", "Thermodynamics", 0.85)

        graph = build_tutoring_graph(ctx)
        state = {
            "student_id": "s_prog",
            "user_input": "Show my learning progress and mastery level",
            "messages": [],
            "conversation_id": "conv_prog_1",
        }

        final = await graph.ainvoke(state)
        assert final["intent"] == "learning_progress"
        assert final.get("lesson") is None

        assistant_msgs = [m for m in final["messages"] if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "85%" in assistant_msgs[-1]["content"]

    @pytest.mark.asyncio
    async def test_off_topic_fast_path(self, ctx):
        ctx.student_repo.get_or_create("s_offtopic")
        graph = build_tutoring_graph(ctx)

        state = {
            "student_id": "s_offtopic",
            "user_input": "What is the recipe for chocolate chip cookies?",
            "messages": [],
            "conversation_id": "conv_off_1",
        }

        final = await graph.ainvoke(state)
        assert final["intent"] == "off_topic"
        assert final.get("lesson") is None

        assistant_msgs = [m for m in final["messages"] if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "studies" in assistant_msgs[-1]["content"].lower()

    @pytest.mark.asyncio
    async def test_tutoring_deep_pipeline(self, ctx):
        ctx.student_repo.get_or_create("s_tutor")
        graph = build_tutoring_graph(ctx)

        state = {
            "student_id": "s_tutor",
            "user_input": "Can you teach me how photosynthesis works?",
            "messages": [],
            "conversation_id": "conv_tutor_1",
        }

        final = await graph.ainvoke(state)
        # Deep tutoring pipeline executes: Planner -> Teacher -> Memory -> Recommendation
        assert final.get("lesson") is not None
        assert final.get("recommendations") is not None
