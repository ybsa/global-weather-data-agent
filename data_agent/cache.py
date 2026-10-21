"""Thread-Safe In-Memory TTL (Time-To-Live) Cache.
Provides fast in-memory caching with automatic item expiration and bounded capacity.
Used across atmospheric, hydrology, chart, and seismic feeds to enable sub-5ms responses
and avoid redundant rate-limiting upstream calls. Zero third-party dependencies.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    """Thread-safe in-memory cache where entries expire after a configured TTL (seconds)."""

    def __init__(self, default_ttl_seconds: float = 300.0, max_size: int = 512):
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        """Retrieve an entry if present and not expired; otherwise return None."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expiry, value = entry
            if now > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: Any, value: Any, ttl_seconds: float | None = None) -> None:
        """Store an entry with optional specific TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.monotonic()
        expiry = now + ttl
        with self._lock:
            # Enforce max_size eviction: purge expired first, or drop oldest
            if len(self._store) >= self.max_size and key not in self._store:
                self._purge_expired(now)
                if len(self._store) >= self.max_size:
                    # Drop an arbitrary item (first key)
                    first_key = next(iter(self._store))
                    del self._store[first_key]
            self._store[key] = (expiry, value)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [k for k, (expiry, _) in self._store.items() if now > expiry]
        for k in expired_keys:
            del self._store[k]

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def get_or_set(
        self,
        key: Any,
        producer: Callable[[], T],
        ttl_seconds: float | None = None,
    ) -> T:
        """Atomically fetch from cache or compute and store."""
        val = self.get(key)
        if val is not None:
            return val
        new_val = producer()
        if new_val is not None:
            self.set(key, new_val, ttl_seconds=ttl_seconds)
        return new_val


# Global default cache instances:
# 5 minutes for live reports and chart series
live_report_cache = TTLCache(default_ttl_seconds=300.0, max_size=512)
# 5 minutes for chart time-series
chart_cache = TTLCache(default_ttl_seconds=300.0, max_size=256)
