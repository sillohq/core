"""
sillo.security.ratelimit.strategies.base — rate-limit algorithm interface.

A strategy is stateless. Given a backend, a key, and the configuration, it
loads the previous state, decides whether the request is allowed, computes the
new state, persists it, and returns a :class:`RateLimitResult`.

All strategies consume **one** token per call. To rate-limit by cost (e.g.
heavy endpoints), pass ``weight > 1`` via ``config.cost``.
"""

from __future__ import annotations

import abc
import typing
import time
from typing import Any, Optional

from typing_extensions import Doc

from ..backends.base import RateLimitBackend, RateLimitResult


class RateLimitStrategy(abc.ABC):
    """Abstract base class for rate-limit algorithms."""

    @abc.abstractmethod
    async def hit(
        self,
        backend: RateLimitBackend,
        key: str,
        limit: int,
        window: int,
        cost: int = 1,
        now: Optional[float] = None,
    ) -> RateLimitResult:
        """Process one request for ``key`` and return the decision."""
        raise NotImplementedError
