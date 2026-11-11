"""High-level RAG service used by the RAG agent and the API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import VectorStoreSettings
from app.core.exceptions import RetrievalError
from app.rag.retrieval.vector_store import VectorStore
from app.schemas.domain import RAGContext, RetrievedChunk
from app.utils.helpers import truncate

if TYPE_CHECKING:
    from app.cache.manager import CacheManager

logger = logging.getLogger(__name__)


class RAGService:
    """Orchestrates the vector store for the rest of the application."""

    def __init__(
        self,
        settings: VectorStoreSettings,
        vector_store: VectorStore | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._settings = settings
        self._store = vector_store or VectorStore(settings, cache_manager=cache_manager)
        self._cache = cache_manager

    # ------------------------------------------------------------- ingest --
    def ingest_chunks(
        self, doc_id: str, chunks: list[dict], student_id: str = ""
    ) -> int:
        """Persist pre-chunked document chunks; returns chunk count."""
        source = chunks[0].get("source", doc_id) if chunks else doc_id
        count = self._store.add_document(
            doc_id, chunks, source=source, student_id=student_id
        )
        if self._cache:
            self._cache.invalidate_student_retrieval(student_id)
        return count

    def delete_document(self, doc_id: str, student_id: str = "") -> None:
        self._store.delete_document(doc_id)
        if self._cache:
            self._cache.invalidate_student_retrieval(student_id)

    # ------------------------------------------------------------ search --
    def search(
        self,
        query: str,
        top_k: int | None = None,
        student_id: str | None = None,
    ) -> list[RetrievedChunk]:
        top_k_val = top_k or self._settings.top_k
        if self._cache:
            cached = self._cache.get_retrieval(
                student_id or "", query, top_k_val, self._settings.collection_name
            )
            if cached is not None:
                logger.debug(
                    "RAG retrieval cache hit for %r (student=%s)",
                    truncate(query, 80),
                    student_id or "all",
                )
                return cached

        chunks = self._store.search(query, top_k=top_k_val, student_id=student_id)
        if self._cache:
            self._cache.set_retrieval(
                student_id or "", query, top_k_val, self._settings.collection_name, chunks
            )

        logger.debug(
            "RAG search for %r (student=%s) returned %d chunks",
            truncate(query, 80),
            student_id or "all",
            len(chunks),
        )
        return chunks

    def build_context(
        self,
        query: str,
        top_k: int | None = None,
        student_id: str | None = None,
    ) -> RAGContext:
        """Return a :class:`RAGContext` with retrieved chunks (possibly empty).

        Retrieval failures never crash the tutoring turn — the context degrades
        to an empty result so the graph can continue without grounding.
        """
        try:
            chunks = self.search(query, top_k=top_k, student_id=student_id)
        except RetrievalError:
            logger.warning("RAG retrieval failed for %r; continuing ungrounded", truncate(query, 80))
            chunks = []
        return RAGContext(retrieved_chunks=chunks, used=bool(chunks))

    # ------------------------------------------------------------- meta ---
    def count(self) -> int:
        return self._store.count()

    def has_document(self, doc_id: str) -> bool:
        return self._store.has_document(doc_id)

    @property
    def settings(self) -> VectorStoreSettings:
        return self._settings
