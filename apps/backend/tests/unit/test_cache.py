"""Unit tests for the caching subsystem (InMemoryLRUCache and CacheManager)."""

from __future__ import annotations

import concurrent.futures
import time

from app.cache.manager import CacheManager
from app.cache.memory import InMemoryLRUCache
from app.core.config import CachingSettings
from app.schemas.domain import RetrievedChunk


class TestInMemoryLRUCache:
    def test_basic_set_get(self):
        cache = InMemoryLRUCache(max_size=5, default_ttl_seconds=3600)
        cache.set("key1", "val1")
        assert cache.get("key1") == "val1"
        assert cache.get("non_existent") is None

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["size"] == 1

    def test_ttl_expiration(self):
        cache = InMemoryLRUCache(max_size=5, default_ttl_seconds=1)
        cache.set("temp_key", "temp_val", ttl_seconds=0.05)
        assert cache.get("temp_key") == "temp_val"

        time.sleep(0.1)
        assert cache.get("temp_key") is None
        stats = cache.stats()
        assert stats["evictions"] >= 1

    def test_lru_eviction_on_capacity(self):
        cache = InMemoryLRUCache(max_size=3, default_ttl_seconds=3600)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access "a" so "b" becomes the least recently used
        assert cache.get("a") == 1

        # Add "d", which should evict "b"
        cache.set("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

        stats = cache.stats()
        assert stats["evictions"] == 1
        assert stats["size"] == 3

    def test_delete_and_pattern_delete(self):
        cache = InMemoryLRUCache(max_size=10, default_ttl_seconds=3600)
        cache.set("student_1:retrieval:q1", "result1")
        cache.set("student_1:retrieval:q2", "result2")
        cache.set("student_2:retrieval:q1", "result3")

        assert cache.delete("student_1:retrieval:q1") is True
        assert cache.delete("non_existent") is False

        # Pattern delete for student_1
        deleted_count = cache.delete_pattern("student_1:*")
        assert deleted_count == 1
        assert cache.get("student_1:retrieval:q2") is None
        assert cache.get("student_2:retrieval:q1") == "result3"

    def test_clear(self):
        cache = InMemoryLRUCache(max_size=10, default_ttl_seconds=3600)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.stats()["size"] == 2

        cache.clear()
        assert cache.stats()["size"] == 0
        assert cache.get("k1") is None

    def test_concurrent_access_thread_safety(self):
        cache = InMemoryLRUCache(max_size=100, default_ttl_seconds=3600)

        def worker(idx: int):
            for i in range(50):
                key = f"key_{idx}_{i}"
                cache.set(key, i)
                val = cache.get(key)
                assert val == i

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, idx) for idx in range(8)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        stats = cache.stats()
        assert stats["sets"] == 400
        assert stats["hits"] == 400


class TestCacheManager:
    def test_embedding_caching(self):
        settings = CachingSettings(enabled=True)
        mgr = CacheManager(settings)

        assert mgr.get_embedding("test_model", "hello world") is None

        vector = [0.1, 0.2, 0.3]
        mgr.set_embedding("test_model", "hello world", vector)

        cached = mgr.get_embedding("test_model", "hello world")
        assert cached == vector

        # Different text produces cache miss
        assert mgr.get_embedding("test_model", "other text") is None

    def test_retrieval_caching_and_student_invalidation(self):
        settings = CachingSettings(enabled=True)
        mgr = CacheManager(settings)

        chunks = [
            RetrievedChunk(content="Photosynthesis details", source="bio.pdf", page=1, score=0.92)
        ]

        mgr.set_retrieval(
            student_id="student_42",
            query="photosynthesis",
            top_k=3,
            collection="notes",
            chunks=chunks,
        )

        cached = mgr.get_retrieval(
            student_id="student_42",
            query="photosynthesis",
            top_k=3,
            collection="notes",
        )
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].content == "Photosynthesis details"

        # Another student querying the same query does not see student_42's cache
        assert (
            mgr.get_retrieval(
                student_id="student_99",
                query="photosynthesis",
                top_k=3,
                collection="notes",
            )
            is None
        )

        # Invalidate student_42 cache
        evicted = mgr.invalidate_student_retrieval("student_42")
        assert evicted == 1
        assert (
            mgr.get_retrieval(
                student_id="student_42",
                query="photosynthesis",
                top_k=3,
                collection="notes",
            )
            is None
        )

    def test_response_cache_disabled_by_default(self):
        settings = CachingSettings(enabled=True, response_cache_enabled=False)
        mgr = CacheManager(settings)

        mgr.set_llm_response("gpt-4o", "Explain gravity", "beginner", "Gravity is a force...")
        assert mgr.get_llm_response("gpt-4o", "Explain gravity", "beginner") is None

    def test_response_cache_when_enabled(self):
        settings = CachingSettings(enabled=True, response_cache_enabled=True)
        mgr = CacheManager(settings)

        mgr.set_llm_response("gpt-4o", "Explain gravity", "beginner", "Gravity is a force...")
        cached = mgr.get_llm_response("gpt-4o", "Explain gravity", "beginner")
        assert cached == "Gravity is a force..."
