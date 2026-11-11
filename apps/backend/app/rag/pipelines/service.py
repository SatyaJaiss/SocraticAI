"""High-level RAG service used by the RAG agent and the API."""

from __future__ import annotations

import logging

from app.core.config import VectorStoreSettings
from app.core.exceptions import RetrievalError
from app.rag.retrieval.vector_store import VectorStore
from app.schemas.domain import RAGContext, RetrievedChunk
from app.utils.helpers import truncate

logger = logging.getLogger(__name__)


class RAGService:
    """Orchestrates the vector store for the rest of the application."""

    def __init__(
        self,
        settings: VectorStoreSettings,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = vector_store or VectorStore(settings)

    # ------------------------------------------------------------- ingest --
    def ingest_chunks(
        self, doc_id: str, chunks: list[dict], student_id: str = ""
    ) -> int:
        """Persist pre-chunked document chunks; returns chunk count."""
        source = chunks[0].get("source", doc_id) if chunks else doc_id
        return self._store.add_document(
            doc_id, chunks, source=source, student_id=student_id
        )

    def delete_document(self, doc_id: str) -> None:
        self._store.delete_document(doc_id)

    # ------------------------------------------------------------ search --
    def search(
        self,
        query: str,
        top_k: int | None = None,
        student_id: str | None = None,
    ) -> list[RetrievedChunk]:
        chunks = self._store.search(query, top_k=top_k, student_id=student_id)
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
