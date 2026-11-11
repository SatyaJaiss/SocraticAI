"""ChromaDB-backed vector store with local embeddings.

Design rationale
----------------
* Embeddings are computed locally (see :mod:`services.rag.embeddings`) and
  handed to ChromaDB explicitly as vectors, so the store never needs to talk to
  an external embedding API and the provider is swappable.
* Chroma ids are ``"{document_id}::{chunk_index}"`` which makes per-document
  delete/replace trivial and keeps the store idempotent on re-ingestion.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import VectorStoreSettings
from app.core.exceptions import RetrievalError
from app.rag.embeddings.provider import EmbeddingProvider, get_embedding_provider
from app.schemas.domain import RetrievedChunk

if TYPE_CHECKING:
    from app.cache.manager import CacheManager

logger = logging.getLogger(__name__)


class VectorStore:
    """Thin, typed wrapper over a persistent ChromaDB collection."""

    def __init__(
        self,
        settings: VectorStoreSettings,
        embedder: EmbeddingProvider | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder or get_embedding_provider(settings)
        self._cache = cache_manager
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - dependency guaranteed
            raise RetrievalError("chromadb is not installed") from exc
        self._client = chromadb.PersistentClient(path=settings.persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Vector store ready: collection=%s path=%s",
            settings.collection_name,
            settings.persist_directory,
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with transparent caching."""
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

    # ------------------------------------------------------------- ingest --
    def add_document(
        self,
        doc_id: str,
        chunks: list[dict],
        *,
        source: str,
        student_id: str = "",
    ) -> int:
        """Embed and store all chunks for one document with student-level isolation.

        ``chunks`` is the list produced by
        :func:`services.rag.chunking.chunk_document_pages` (each a
        ``{"text", "page", "source"}`` dict). Re-ingesting the same ``doc_id``
        replaces the previous chunks. Returns the number of chunks stored.
        """
        if not chunks:
            return 0
        texts = [c["text"] for c in chunks]
        try:
            vectors = self._embed(texts)
        except Exception as exc:
            raise RetrievalError(f"Embedding failed for {doc_id}: {exc}") from exc

        ids = [f"{doc_id}::{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "student_id": student_id,
                "source": c.get("source", source),
                "page": int(c["page"]) if c.get("page") is not None else None,
            }
            for c in chunks
        ]

        # Idempotent re-ingest: drop any previous chunks for this document first.
        try:
            self._collection.delete(where={"doc_id": doc_id})
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            logger.debug("Cleanup delete for %s failed: %s", doc_id, exc)

        self._collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(
            "Stored %d chunks for document %s (student=%s)",
            len(chunks),
            doc_id,
            student_id or "unassigned",
        )
        return len(chunks)

    # ------------------------------------------------------------ search --
    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        student_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Semantic search over the collection, returning ranked chunks.

        When ``student_id`` is supplied, chunks are strictly filtered to ensure
        student data isolation.
        """
        if self._collection.count() == 0:
            return []
        top_k = top_k or self._settings.top_k
        try:
            query_vector = self._embed([query])[0]
        except Exception as exc:
            raise RetrievalError(f"Query embedding failed: {exc}") from exc

        query_kwargs: dict = {
            "query_embeddings": [query_vector],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if student_id:
            query_kwargs["where"] = {"student_id": student_id}

        try:
            result = self._collection.query(**query_kwargs)
        except Exception as exc:
            raise RetrievalError(f"Vector search failed: {exc}") from exc

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        chunks: list[RetrievedChunk] = []
        for text, meta_row, distance in zip(documents, metadatas, distances, strict=False):
            metadata = meta_row or {}
            # Chroma cosine distance is 1 - cosine similarity.
            score = round(max(0.0, 1.0 - float(distance)), 4)
            chunks.append(
                RetrievedChunk(
                    content=str(text),
                    source=str(metadata.get("source", "unknown")),
                    page=int(metadata["page"]) if metadata.get("page") is not None else None,
                    score=score,
                )
            )
        return chunks

    # ------------------------------------------------------------ delete --
    def delete_document(self, doc_id: str) -> None:
        """Remove every chunk belonging to ``doc_id``."""
        try:
            self._collection.delete(where={"doc_id": doc_id})
        except Exception as exc:
            raise RetrievalError(f"Failed to delete document {doc_id}: {exc}") from exc

    # ------------------------------------------------------------- meta ---
    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception as exc:  # pragma: no cover - defensive
            raise RetrievalError(f"Vector store count failed: {exc}") from exc

    def has_document(self, doc_id: str) -> bool:
        try:
            result = self._collection.get(
                where={"doc_id": doc_id}, limit=1, include=[]
            )
            return bool(result and result.get("ids"))
        except Exception:  # pragma: no cover - defensive
            return False

    @property
    def settings(self) -> VectorStoreSettings:
        return self._settings
