"""
sillo.security.ratelimit.backends.memory — process-local in-memory backend.

Suitable for single-instance deployments and tests. Uses an ``asyncio.Lock``
to make read-modify-write safe across concurrent coroutines within one process.
State is expired lazily by timestamp, so no background cleanup task is required.
"""

from __future__ import annotations

import asyncio
import time

from .base import RateLimitBackend


class InMemoryBackend(RateLimitBackend):
    """Store rate-limit state in a plain dict scoped to the current process."""

    def __init__(self) -> None:
        """Init"""
        self._store: dict[str, tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    async def fetch_state(self, key: str) -> dict | None:
        """Fetch State"""
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            state, expires_at = item
            if expires_at <= time.time():
                self._store.pop(key, None)
                return None
            return state

    async def save_state(self, key: str, state: dict, ttl: int) -> None:
        """Save State"""
        async with self._lock:
            self._store[key] = (state, time.time() + ttl)

    async def clear(self) -> None:
        """Clear"""
        async with self._lock:
            self._store.clear()
