"""High-level cache manager with typed namespaces and invalidation hooks."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.cache.base import BaseCacheBackend
from app.cache.memory import InMemoryLRUCache
from app.core.config import CachingSettings
from app.schemas.domain import RetrievedChunk

logger = logging.getLogger(__name__)


def _hash_key(*parts: str) -> str:
    """Compute deterministic SHA-256 hex digest for key components."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()[:32]


class CacheManager:
    """Central cache coordinator managing embeddings, retrieval, and LLM responses."""

    def __init__(
        self,
        settings: CachingSettings,
        backend: BaseCacheBackend | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend or InMemoryLRUCache(
            max_size=settings.max_size,
            default_ttl_seconds=settings.default_ttl_seconds,
        )

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    @property
    def backend(self) -> BaseCacheBackend:
        return self._backend

    # -------------------------------------------------------- Embeddings -- #
    def get_embedding(self, model: str, text: str) -> list[float] | None:
        if not self.enabled:
            return None
        key = f"emb:{model}:{_hash_key(text.strip())}"
        return self._backend.get(key)

    def set_embedding(
        self,
        model: str,
        text: str,
        vector: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        if not self.enabled:
            return
        key = f"emb:{model}:{_hash_key(text.strip())}"
        ttl = ttl_seconds or self._settings.embedding_cache_ttl_seconds
        self._backend.set(key, vector, ttl_seconds=ttl)

    # --------------------------------------------------------- Retrieval -- #
    def make_retrieval_key(
        self,
        student_id: str,
        query: str,
        top_k: int,
        collection: str,
    ) -> str:
        query_hash = _hash_key(query.strip().lower(), str(top_k), collection)
        return f"ret:{student_id or 'all'}:{query_hash}"

    def get_retrieval(
        self,
        student_id: str,
        query: str,
        top_k: int,
        collection: str,
    ) -> list[RetrievedChunk] | None:
        if not self.enabled:
            return None
        key = self.make_retrieval_key(student_id, query, top_k, collection)
        cached = self._backend.get(key)
        if cached is None:
            return None
        # Return deep copy of chunks
        return [
            RetrievedChunk(
                content=c.content,
                source=c.source,
                page=c.page,
                score=c.score,
            )
            for c in cached
        ]

    def set_retrieval(
        self,
        student_id: str,
        query: str,
        top_k: int,
        collection: str,
        chunks: list[RetrievedChunk],
        ttl_seconds: int | None = None,
    ) -> None:
        if not self.enabled:
            return
        key = self.make_retrieval_key(student_id, query, top_k, collection)
        ttl = ttl_seconds or self._settings.retrieval_cache_ttl_seconds
        self._backend.set(key, chunks, ttl_seconds=ttl)

    def invalidate_student_retrieval(self, student_id: str) -> int:
        """Evict all cached retrieval queries for a specific student."""
        pattern = f"ret:{student_id or 'all'}:*"
        evicted = self._backend.delete_pattern(pattern)
        logger.debug("Invalidated %d retrieval cache entries for student %s", evicted, student_id)
        return evicted

    # ----------------------------------------------------- LLM Responses -- #
    def get_llm_response(self, model: str, prompt: str, student_level: str) -> str | None:
        if not self.enabled or not self._settings.response_cache_enabled:
            return None
        key = f"resp:{model}:{student_level}:{_hash_key(prompt.strip())}"
        return self._backend.get(key)

    def set_llm_response(
        self,
        model: str,
        prompt: str,
        student_level: str,
        response: str,
        ttl_seconds: int | None = None,
    ) -> None:
        if not self.enabled or not self._settings.response_cache_enabled:
            return
        key = f"resp:{model}:{student_level}:{_hash_key(prompt.strip())}"
        ttl = ttl_seconds or self._settings.response_cache_ttl_seconds
        self._backend.set(key, response, ttl_seconds=ttl)

    # ----------------------------------------------------------- General -- #
    def clear(self) -> None:
        self._backend.clear()

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "response_cache_enabled": self._settings.response_cache_enabled,
            **self._backend.stats(),
        }
