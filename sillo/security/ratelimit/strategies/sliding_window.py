"""
sillo.security.ratelimit.strategies.sliding_window — sliding-window log.

Tracks individual request timestamps and only counts those within the last
``window`` seconds. This eliminates the boundary double-count problem of the
fixed window: a client is limited to ``limit`` requests in *any* trailing
window of ``window`` seconds. More accurate, but state grows with request
volume (pruned each hit).
"""

from __future__ import annotations

import time

from ..backends.base import RateLimitBackend, RateLimitResult
from .base import RateLimitStrategy


class SlidingWindowStrategy(RateLimitStrategy):
    """Count only the timestamps that fall inside the trailing window."""

    async def hit(
        self,
        backend: RateLimitBackend,
        key: str,
        limit: int,
        window: int,
        cost: int = 1,
        now: float | None = None,
    ) -> RateLimitResult:
        """Hit"""
        now = now if now is not None else time.time()
        cutoff = now - window
        state = await backend.fetch_state(key)
        hits: list[float] = (state or {}).get("hits", [])
        hits = [t for t in hits if t > cutoff]
        if len(hits) + cost > limit:
            # Oldest timestamp defines when a slot frees up.
            retry_after = int(hits[0] + window - now) + 1
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=max(limit - len(hits), 0),
                reset_at=hits[0] + window,
                retry_after=retry_after,
            )
        new_hits = hits + [now] * cost
        await backend.save_state(key, {"hits": new_hits}, ttl=window)
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=max(limit - len(new_hits), 0),
            reset_at=(new_hits[0] + window if new_hits else now + window),
            retry_after=0,
        )
