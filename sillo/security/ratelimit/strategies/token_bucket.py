"""
sillo.security.ratelimit.strategies.token_bucket — token-bucket algorithm.

Maintains a bucket of ``limit`` tokens refilled at a steady rate of
``limit / window`` tokens per second. Each request consumes one (or ``cost``)
tokens. Allows short bursts up to ``limit`` then smoothly throttles. The
default strategy for :class:`RateLimitMiddleware` because it gives the smoothest
client experience.
"""

from __future__ import annotations

import typing
import time
from typing import Any, Optional

from typing_extensions import Doc

from ..backends.base import RateLimitBackend, RateLimitResult
from .base import RateLimitStrategy


class TokenBucketStrategy(RateLimitStrategy):
    """Refill ``limit`` tokens across ``window`` seconds, consume per hit."""

    async def hit(
        self,
        backend: RateLimitBackend,
        key: str,
        limit: int,
        window: int,
        cost: int = 1,
        now: Optional[float] = None,
    ) -> RateLimitResult:
        """Hit

        Args:
            backend: [description]
            key: [description]
            limit: [description]
            window: [description]
            cost: [description]
            now: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        now = now if now is not None else time.time()
        refill_rate = limit / window  # tokens per second
        state = await backend.fetch_state(key)
        if state is None:
            state = {"tokens": float(limit), "last": now}
        elapsed = now - state["last"]
        tokens = min(limit, state["tokens"] + elapsed * refill_rate)
        if tokens < cost:
            deficit = cost - tokens
            retry_after = int(deficit / refill_rate) + 1
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=max(int(tokens), 0),
                reset_at=now + deficit / refill_rate,
                retry_after=retry_after,
            )
        tokens -= cost
        await backend.save_state(key, {"tokens": tokens, "last": now}, ttl=window * 2)
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=max(int(tokens), 0),
            reset_at=now + (limit - tokens) / refill_rate,
            retry_after=0,
        )
