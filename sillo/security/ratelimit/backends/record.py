"""
sillo.security.ratelimit.backends.record — sillo Record (ORM) backend.

Stores rate-limit state in the application database via ``sillo.record``. Use
this when you want persistence without an external cache and can tolerate
single-instance-level atomicity. The ``RateLimitCounter`` model must be
registered with your Record setup (see ``sillo.security.ratelimit.models``).
"""

from __future__ import annotations

from ..models import RateLimitCounter
from .base import RateLimitBackend


class RecordBackend(RateLimitBackend):
    """Persist rate-limit state using the sillo Record ORM."""

    async def fetch_state(self, key: str) -> dict | None:
        """Fetch State"""
        return await RateLimitCounter.fetch(key)

    async def save_state(self, key: str, state: dict, ttl: int) -> None:
        """Save State"""
        await RateLimitCounter.save_state(key, state, ttl)

    async def clear(self) -> None:
        """Clear"""
        await RateLimitCounter.clear_all()
