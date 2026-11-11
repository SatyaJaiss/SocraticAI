"""Unit tests for token-aware ContextBuilder."""

from __future__ import annotations

from app.context.builder import ContextBuilder
from app.core.config import ContextBudgetSettings
from app.schemas.domain import EpisodicMemory, RetrievedChunk


class TestContextBuilder:
    def test_token_counting(self):
        settings = ContextBudgetSettings()
        builder = ContextBuilder(settings)

        assert builder.count_tokens("") == 0
        count = builder.count_tokens("Hello, this is a test prompt for SocraticAI tutoring.")
        assert count > 5

    def test_section_budgets_respected(self):
        settings = ContextBudgetSettings(
            system_prompt_budget=20,
            history_budget=30,
            episodic_memory_budget=25,
            semantic_profile_budget=25,
            rag_budget=40,
            total_budget=500,
        )
        builder = ContextBuilder(settings)

        # Huge system prompt
        huge_system = "You are a teacher. " * 50
        # Long history
        history = [
            {"role": "user", "content": f"Message turn {i} with lots of conversational detail."}
            for i in range(15)
        ]
        # Episodic memories
        memories = [
            EpisodicMemory(
                id=i,
                student_id="s1",
                topic=f"Topic {i}",
                summary=f"Summary of past session {i} explaining complex concepts in detail.",
                created_at="2026-11-12T00:00:00Z",
            )
            for i in range(5)
        ]
        # Semantic profile
        profile = {
            "level": "intermediate",
            "active_misconceptions": [
                {"concept": f"Concept {i}", "description": f"Misconception explanation {i}"}
                for i in range(5)
            ],
            "weak_concepts": ["Calculus", "Physics", "Chemistry"],
        }
        # RAG chunks
        chunks = [
            RetrievedChunk(
                content=f"Extracted document chunk content number {i} " * 10,
                source=f"doc_{i}.pdf",
                page=i,
                score=0.9,
            )
            for i in range(5)
        ]

        result = builder.build_context(
            system_prompt=huge_system,
            user_message="Can you teach me thermodynamics?",
            history_messages=history,
            episodic_memories=memories,
            semantic_profile=profile,
            rag_chunks=chunks,
        )

        # Verify budgets
        assert result.token_counts["system_prompt"] <= settings.system_prompt_budget + 2
        assert result.token_counts["history"] <= settings.history_budget + 2
        assert result.token_counts["episodic_memory"] <= settings.episodic_memory_budget + 2
        assert result.token_counts["semantic_profile"] <= settings.semantic_profile_budget + 2
        assert result.token_counts["rag"] <= settings.rag_budget + 2

        # Verify truncation was tracked
        assert "system_prompt" in result.truncated_sections
        assert "history" in result.truncated_sections
        assert "episodic_memory" in result.truncated_sections

        # Verify newest history was kept over oldest
        assert len(result.history_messages) < len(history)
        # Last message in original history should be the last message in result.history_messages
        assert result.history_messages[-1]["content"] == history[-1]["content"]

        # Verify source traceability
        assert any("episodic_memory:" in s for s in result.sources_included)
        assert any("misconception:" in s for s in result.sources_included)
        assert any("doc:" in s for s in result.sources_included)

    def test_minimal_prompt_assembly(self):
        settings = ContextBudgetSettings()
        builder = ContextBuilder(settings)

        result = builder.build_context(
            system_prompt="You are SocraticAI.",
            user_message="Hello!",
        )

        assert "Student: Hello!" in result.assembled_prompt
        assert result.token_counts["history"] == 0
        assert result.token_counts["rag"] == 0
        assert not result.truncated_sections
