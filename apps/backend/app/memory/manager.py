"""Unified MemoryManager coordinating working, episodic, and semantic memory layers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.config import MemorySettings, VectorStoreSettings
from app.db.connection import Database
from app.memory.episodic import EpisodicMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.schemas.domain import EpisodicMemory

if TYPE_CHECKING:
    from app.cache.manager import CacheManager
    from app.llm.clients.client import LLMClient

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates working memory, cross-session episodic memory, and semantic student profiles."""

    def __init__(
        self,
        db: Database,
        memory_settings: MemorySettings,
        vector_settings: VectorStoreSettings,
        episodic_store: EpisodicMemoryStore | None = None,
        semantic_store: SemanticMemoryStore | None = None,
        llm: LLMClient | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._db = db
        self._settings = memory_settings
        self._episodic = episodic_store or EpisodicMemoryStore(
            db=db,
            memory_settings=memory_settings,
            vector_settings=vector_settings,
            cache_manager=cache_manager,
        )
        self._semantic = semantic_store or SemanticMemoryStore(db=db)
        self._llm = llm

    @property
    def episodic(self) -> EpisodicMemoryStore:
        return self._episodic

    @property
    def semantic(self) -> SemanticMemoryStore:
        return self._semantic

    # ------------------------------------------------ Cross-Session Query -- #
    def retrieve_contextual_memories(self, student_id: str, query: str) -> dict[str, Any]:
        """Fetch both relevant episodic narrative memories and current semantic profile."""
        episodic_matches = self._episodic.search_memories(
            student_id=student_id,
            query=query,
            top_k=self._settings.episodic_top_k,
            threshold=self._settings.memory_similarity_threshold,
        )
        semantic_profile = self._semantic.get_semantic_profile(student_id)

        return {
            "episodic_memories": episodic_matches,
            "semantic_profile": semantic_profile,
        }

    # --------------------------------------------------- Consolidation -- #
    async def consolidate_session(
        self,
        student_id: str,
        session_id: str,
        messages: list[dict[str, Any]],
        topic: str = "",
    ) -> EpisodicMemory | None:
        """Summarize conversation messages and persist into episodic and semantic stores."""
        if not messages or len(messages) < 2:
            return None

        # Build transcript text
        transcript_lines = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            transcript_lines.append(f"{role.capitalize()}: {content}")
        transcript = "\n".join(transcript_lines)

        summary = ""
        # If LLM available, generate a concise learning summary
        if self._llm is not None:
            prompt = (
                "Summarize the following tutoring interaction in 2-3 sentences. Focus on what the student learned, "
                "concepts they struggled with, and key milestones achieved:\n\n"
                f"{transcript[:3000]}"
            )
            try:
                summary = await self._llm.agenerate(
                    system_prompt="You are an expert educational memory consolidating agent. Be factual, concise, and pedagogical.",
                    user_prompt=prompt,
                )
            except Exception as exc:
                logger.warning(
                    "LLM memory consolidation failed, falling back to rule-based: %s", exc
                )

        if not summary:
            # Deterministic fallback summary
            summary = f"Session covering {topic or 'general concepts'}. Discussed {len(messages)} interaction turns."

        memory = self._episodic.add_memory(
            student_id=student_id,
            summary=summary.strip(),
            topic=topic,
            session_id=session_id,
            event_type="conversation_summary",
            provenance={"message_count": len(messages)},
        )
        logger.info(
            "Consolidated episodic memory for student %s (session %s)",
            student_id,
            session_id,
        )
        return memory
