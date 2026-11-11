"""Integration tests for EpisodicMemoryStore, SemanticMemoryStore, and MemoryManager."""

from __future__ import annotations

import pytest
from app.core.config import MemorySettings, VectorStoreSettings
from app.db.connection import Database
from app.memory.episodic import EpisodicMemoryStore
from app.memory.manager import MemoryManager
from app.memory.semantic import SemanticMemoryStore
from app.schemas.enums import StudentLevel


class TestEpisodicMemoryStore:
    @pytest.fixture
    def memory_store(self, tmp_path) -> EpisodicMemoryStore:
        from app.core.config import DatabaseSettings
        from app.repositories.student_repository import StudentRepository

        db_settings = DatabaseSettings(url="sqlite:///:memory:")
        real_db = Database(db_settings)
        real_db.create_schema()

        # Seed students for foreign key constraints
        repo = StudentRepository(real_db)
        repo.create(student_id="student_einstein", name="Albert")
        repo.create(student_id="student_alice", name="Alice")
        repo.create(student_id="student_bob", name="Bob")

        mem_settings = MemorySettings(
            episodic_collection_name="test_episodic_memories",
            episodic_top_k=3,
            memory_similarity_threshold=0.3,
        )
        vec_settings = VectorStoreSettings(
            persist_directory=str(tmp_path / "chroma"),
            collection_name="test_episodic_memories",
        )

        return EpisodicMemoryStore(
            db=real_db,
            memory_settings=mem_settings,
            vector_settings=vec_settings,
        )

    def test_add_and_retrieve_episodic_memory(self, memory_store):
        # Student 1 stores memories
        mem1 = memory_store.add_memory(
            student_id="student_einstein",
            topic="Special Relativity",
            summary="Explored time dilation and Lorentz transformations at relativistic velocities.",
            session_id="sess_1",
        )
        assert mem1.id is not None
        assert mem1.student_id == "student_einstein"

        # List recent
        recent = memory_store.list_recent("student_einstein")
        assert len(recent) == 1
        assert recent[0].topic == "Special Relativity"

        # Semantic search
        matches = memory_store.search_memories(
            student_id="student_einstein",
            query="Lorentz time dilation",
        )
        assert len(matches) >= 1
        assert "Lorentz" in matches[0].summary

    def test_student_data_isolation_in_episodic_memory(self, memory_store):
        # Student A stores physics memories
        memory_store.add_memory(
            student_id="student_alice",
            topic="Quantum Mechanics",
            summary="Understood wave-particle duality and the Heisenberg uncertainty principle.",
        )

        # Student B stores history memories
        memory_store.add_memory(
            student_id="student_bob",
            topic="Ancient Rome",
            summary="Covered the transition from the Roman Republic to the Roman Empire under Augustus.",
        )

        # Student Alice searches for Roman history — must NOT see Bob's memories
        alice_results = memory_store.search_memories(
            student_id="student_alice",
            query="Roman Republic Augustus",
        )
        assert len(alice_results) == 0

        # Student Bob searches for Roman history — gets his own memory
        bob_results = memory_store.search_memories(
            student_id="student_bob",
            query="Roman Republic Augustus",
        )
        assert len(bob_results) == 1
        assert "Augustus" in bob_results[0].summary


class TestSemanticMemoryStore:
    @pytest.fixture
    def semantic_store(self) -> tuple[SemanticMemoryStore, Database]:
        from app.core.config import DatabaseSettings

        db = Database(DatabaseSettings(url="sqlite:///:memory:"))
        db.create_schema()
        store = SemanticMemoryStore(db)
        return store, db

    def test_record_and_resolve_misconception(self, semantic_store):
        store, db = semantic_store
        from app.repositories.student_repository import StudentRepository

        repo = StudentRepository(db)
        repo.create(student_id="student_curie", name="Marie")

        # Record misconception
        misc = store.record_misconception(
            student_id="student_curie",
            concept="Fractions Addition",
            description="Adds numerators and denominators across directly (e.g. 1/2 + 1/3 = 2/5).",
            severity="high",
            confidence=0.9,
            provenance={"quiz_id": "quiz_math_1"},
        )
        assert misc.id is not None
        assert misc.status == "active"
        assert misc.severity == "high"

        # List active misconceptions
        active = store.list_active_misconceptions("student_curie")
        assert len(active) == 1
        assert active[0].concept == "Fractions Addition"

        # Resolve misconception
        resolved = store.resolve_misconception(misc.id)
        assert resolved is True

        # Now active list is empty
        active_after = store.list_active_misconceptions("student_curie")
        assert len(active_after) == 0

    def test_get_semantic_profile(self, semantic_store):
        store, db = semantic_store
        from app.repositories.student_repository import StudentRepository

        repo = StudentRepository(db)
        repo.create(
            student_id="student_feynman", name="Richard", level=StudentLevel.INTERMEDIATE.value
        )
        repo.upsert_concept_score("student_feynman", "Electrodynamics", 0.95)
        repo.upsert_concept_score("student_feynman", "Complex Analysis", 0.45)
        repo.add_topic_learned("student_feynman", "Electromagnetism")

        store.record_misconception(
            student_id="student_feynman",
            concept="Path Integrals",
            description="Confused classical action with quantum phase.",
        )

        profile = store.get_semantic_profile("student_feynman")
        assert profile["student_id"] == "student_feynman"
        assert profile["level"] == "intermediate"
        assert "Electrodynamics" in profile["strong_concepts"]
        assert "Complex Analysis" in profile["weak_concepts"]
        assert len(profile["active_misconceptions"]) == 1


class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_session_consolidation(self, tmp_path):
        from app.core.config import DatabaseSettings
        from app.llm.providers.demo import DemoLLMClient
        from app.repositories.student_repository import StudentRepository

        db = Database(DatabaseSettings(url="sqlite:///:memory:"))
        db.create_schema()

        repo = StudentRepository(db)
        repo.create(student_id="student_bio", name="Gregor")

        mem_settings = MemorySettings()
        vec_settings = VectorStoreSettings(persist_directory=str(tmp_path / "chroma"))

        from app.core.config import LLMSettings

        llm = DemoLLMClient(LLMSettings(provider="demo"))
        mgr = MemoryManager(
            db=db,
            memory_settings=mem_settings,
            vector_settings=vec_settings,
            llm=llm,
        )

        messages = [
            {"role": "user", "content": "Can you explain how cellular mitosis works?"},
            {
                "role": "assistant",
                "content": "Mitosis is divided into prophase, metaphase, anaphase, and telophase.",
            },
            {"role": "user", "content": "I understand metaphase now, thank you!"},
        ]

        memory = await mgr.consolidate_session(
            student_id="student_bio",
            session_id="session_101",
            messages=messages,
            topic="Mitosis",
        )

        assert memory is not None
        assert memory.student_id == "student_bio"
        assert memory.session_id == "session_101"
        assert memory.topic == "Mitosis"
        assert len(memory.summary) > 10
