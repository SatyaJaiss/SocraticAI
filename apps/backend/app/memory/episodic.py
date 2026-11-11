"""Cross-session episodic memory store backed by SQLite and ChromaDB with student data isolation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select

from app.core.config import MemorySettings, VectorStoreSettings
from app.core.exceptions import RetrievalError
from app.db.connection import Database
from app.models.orm import EpisodicMemoryRow
from app.rag.embeddings.provider import EmbeddingProvider, get_embedding_provider
from app.schemas.domain import EpisodicMemory
from app.utils.helpers import utc_now_iso

if TYPE_CHECKING:
    from app.cache.manager import CacheManager

logger = logging.getLogger(__name__)


class EpisodicMemoryStore:
    """Manages cross-session narrative memories with dual SQLite + ChromaDB persistence."""

    def __init__(
        self,
        db: Database,
        memory_settings: MemorySettings,
        vector_settings: VectorStoreSettings,
        embedder: EmbeddingProvider | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._db = db
        self._memory_settings = memory_settings
        self._vector_settings = vector_settings
        self._embedder = embedder or get_embedding_provider(vector_settings)
        self._cache = cache_manager

        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover
            raise RetrievalError("chromadb is required for EpisodicMemoryStore") from exc

        self._client = chromadb.PersistentClient(path=vector_settings.persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=memory_settings.episodic_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Episodic memory store ready: collection=%s",
            memory_settings.episodic_collection_name,
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._cache:
            return self._embedder.embed_texts(texts)

        model_name = getattr(self._embedder, "name", "default")
        results: list[list[float] | None] = [
            self._cache.get_embedding(model_name, t) for t in texts
        ]
        missing_indices = [i for i, r in enumerate(results) if r is None]
        if missing_indices:
            missing_texts = [texts[i] for i in missing_indices]
            computed = self._embedder.embed_texts(missing_texts)
            for idx, vec in zip(missing_indices, computed, strict=False):
                results[idx] = vec
                self._cache.set_embedding(model_name, texts[idx], vec)
        return [r for r in results if r is not None]

    # ------------------------------------------------------------- Store -- #
    def add_memory(
        self,
        student_id: str,
        summary: str,
        *,
        topic: str = "",
        session_id: str | None = None,
        event_type: str = "conversation_summary",
        provenance: dict[str, Any] | None = None,
    ) -> EpisodicMemory:
        """Persist a narrative memory in SQLite and index its vector embedding in ChromaDB."""
        now = utc_now_iso()
        provenance_data = provenance or {}

        # 1. SQLite persistent record
        with self._db.session() as session:
            row = EpisodicMemoryRow(
                student_id=student_id,
                session_id=session_id,
                topic=topic,
                summary=summary,
                event_type=event_type,
                provenance=provenance_data,
                created_at=now,
            )
            session.add(row)
            session.flush()
            memory_id = row.id

        # 2. ChromaDB semantic vector index
        doc_text = f"Topic: {topic}\nSummary: {summary}" if topic else summary
        try:
            vector = self._embed([doc_text])[0]
            self._collection.add(
                ids=[f"mem_{memory_id}"],
                embeddings=[vector],
                documents=[doc_text],
                metadatas=[
                    {
                        "student_id": student_id,
                        "memory_id": str(memory_id),
                        "session_id": session_id or "",
                        "topic": topic,
                        "event_type": event_type,
                    }
                ],
            )
        except Exception as exc:
            logger.warning("Failed to index episodic memory %d into ChromaDB: %s", memory_id, exc)

        return EpisodicMemory(
            id=memory_id,
            student_id=student_id,
            session_id=session_id,
            topic=topic,
            summary=summary,
            event_type=event_type,
            provenance=provenance_data,
            created_at=now,
        )

    # ------------------------------------------------------------ Search -- #
    def search_memories(
        self,
        student_id: str,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[EpisodicMemory]:
        """Retrieve relevant past memories strictly isolated to the requesting student."""
        if self._collection.count() == 0:
            return []

        limit = top_k or self._memory_settings.episodic_top_k
        min_threshold = (
            threshold
            if threshold is not None
            else self._memory_settings.memory_similarity_threshold
        )

        try:
            query_vector = self._embed([query])[0]
            result = self._collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where={"student_id": student_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("Episodic memory vector search failed: %s", exc)
            return []

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        matched_memories: list[EpisodicMemory] = []
        for doc, meta_row, dist in zip(documents, metadatas, distances, strict=False):
            metadata = meta_row or {}
            # Cosine distance = 1 - similarity
            similarity = round(max(0.0, 1.0 - float(dist)), 4)
            if similarity < min_threshold:
                continue

            raw_id = metadata.get("memory_id")
            memory_id = int(raw_id) if (raw_id and str(raw_id).isdigit()) else raw_id

            matched_memories.append(
                EpisodicMemory(
                    id=memory_id or "unknown",
                    student_id=student_id,
                    session_id=metadata.get("session_id") or None,
                    topic=str(metadata.get("topic", "")),
                    summary=str(doc),
                    event_type=str(metadata.get("event_type", "conversation_summary")),
                    provenance={},
                    created_at="",
                    score=similarity,
                )
            )

        return matched_memories

    # ------------------------------------------------------------- List -- #
    def list_recent(self, student_id: str, limit: int = 10) -> list[EpisodicMemory]:
        """Fetch the latest episodic memories from SQLite."""
        with self._db.session() as session:
            rows = (
                session.execute(
                    select(EpisodicMemoryRow)
                    .where(EpisodicMemoryRow.student_id == student_id)
                    .order_by(desc(EpisodicMemoryRow.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            return [
                EpisodicMemory(
                    id=r.id,
                    student_id=r.student_id,
                    session_id=r.session_id,
                    topic=r.topic,
                    summary=r.summary,
                    event_type=r.event_type,
                    provenance=r.provenance or {},
                    created_at=r.created_at,
                )
                for r in rows
            ]
