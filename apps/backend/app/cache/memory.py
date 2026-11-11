"""Thread-safe in-memory LRU cache backend with TTL support."""

from __future__ import annotations

import fnmatch
import threading
import time
from collections import OrderedDict
from typing import Any

from app.cache.base import BaseCacheBackend


class _CacheEntry:
    __slots__ = ("expires_at", "value")

    def __init__(self, value: Any, expires_at: float | None = None) -> None:
        self.value = value
        self.expires_at = expires_at

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and now > self.expires_at


class InMemoryLRUCache(BaseCacheBackend):
    """Thread-safe in-memory LRU cache with per-item TTL expiration and metrics."""

    def __init__(self, max_size: int = 10000, default_ttl_seconds: int = 3600) -> None:
        self._max_size = max(1, max_size)
        self._default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._sets = 0

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired(now):
                del self._cache[key]
                self._misses += 1
                self._evictions += 1
                return None
            # Move to end to indicate recent use (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        now = time.monotonic()
        expires_at = now + ttl if ttl and ttl > 0 else None
        entry = _CacheEntry(value, expires_at)

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = entry
            self._sets += 1

            # Evict if over max capacity
            while len(self._cache) > self._max_size:
                # Pop oldest (first item in OrderedDict)
                self._cache.popitem(last=False)
                self._evictions += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def delete_pattern(self, pattern: str) -> int:
        count = 0
        with self._lock:
            matching_keys = [k for k in self._cache if fnmatch.fnmatchcase(k, pattern)]
            for k in matching_keys:
                del self._cache[k]
                count += 1
        return count

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "sets": self._sets,
                "size": len(self._cache),
                "max_size": self._max_size,
            }
