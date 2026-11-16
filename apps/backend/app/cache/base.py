"""Base cache abstraction interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCacheBackend(ABC):
    """Abstract interface for all caching backends (in-memory, Redis, etc.)."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve a cached item by key, returning None if missing or expired."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store an item in the cache with an optional time-to-live."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an item by key. Returns True if key existed."""

    @abstractmethod
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a wildcard pattern (e.g. 'prefix:*').

        Returns the count of deleted items.
        """

    @abstractmethod
    def clear(self) -> None:
        """Evict all cached entries."""

    @abstractmethod
    def stats(self) -> dict[str, int]:
        """Return operational metrics (hits, misses, evictions, current size)."""

