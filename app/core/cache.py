import time
import functools
from typing import Any, Callable, Dict, Tuple


class SimpleMemoryCache:
    """In-memory TTL cache with automatic expiration for fast DB read acceleration."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        value, expires_at = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._cache[key] = (value, time.time() + ttl)

    def invalidate(self, prefix: str = "") -> None:
        if not prefix:
            self._cache.clear()
            return
        keys_to_del = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_del:
            del self._cache[k]


cache = SimpleMemoryCache(default_ttl_seconds=60.0)
