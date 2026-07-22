"""
sillo.security.ratelimit.strategies.fixed_window — fixed-window counter.

Simplest algorithm: count requests within a rolling ``window`` starting at the
first hit. Resets completely when the window elapses. Allows bursts at window
boundaries (the classic "double count" at the edge) but is cheap and
predictable.
"""

from __future__ import annotations

import typing
import time
from typing import Any, Optional

from typing_extensions import Doc

from ..backends.base import RateLimitBackend, RateLimitResult
from .base import RateLimitStrategy


class FixedWindowStrategy(RateLimitStrategy):
    """Count requests in a fixed time window keyed by ``window_start``."""

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
        window_start = int(now // window) * window
        state = await backend.fetch_state(key)
        if state is None or state.get("window_start") != window_start:
            state = {"window_start": window_start, "count": 0}
        count = state["count"]
        reset_at = window_start + window
        if count + cost > limit:
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=max(limit - count, 0),
                reset_at=reset_at,
                retry_after=int(reset_at - now) + 1,
            )
        new_count = count + cost
        await backend.save_state(
            key, {"window_start": window_start, "count": new_count}, ttl=window
        )
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=max(limit - new_count, 0),
            reset_at=reset_at,
            retry_after=0,
        )
