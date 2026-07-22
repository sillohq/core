"""
sillo.security.ratelimit.backends.base — backend interface and result types.

A *backend* is a key/value store that persists rate-limit state between
requests. Strategies are stateless: they serialize their own state as a plain
dict and ask the backend to fetch/save it. This keeps memory, Redis, and
Record backends trivially interchangeable.
"""

from __future__ import annotations

import time
import typing
from dataclasses import dataclass
from typing import Any, Optional

from typing_extensions import Doc


@dataclass
class RateLimitResult:
    """The outcome of a single rate-limit decision."""

    allowed: bool
    """Whether the request is permitted."""

    limit: int
    """The configured maximum requests in the window."""

    remaining: int
    """Requests left in the current window."""

    reset_at: float
    """Unix timestamp (seconds) when the window/counter resets."""

    retry_after: int
    """Seconds the client should wait before retrying (0 when allowed)."""


class RateLimitBackend:
    """Abstract base class for rate-limit backends."""

    async def fetch_state(self, key: str) -> Optional[dict]:
        """Return the stored state dict for ``key`` or ``None`` if absent/expired."""
        raise NotImplementedError

    async def save_state(self, key: str, state: dict, ttl: int) -> None:
        """Persist ``state`` for ``key`` with a TTL of ``ttl`` seconds."""
        raise NotImplementedError

    async def clear(self) -> None:
        """Drop all stored state (used by tests and admin tooling)."""
        raise NotImplementedError


def _now() -> float:
    """Now

    Returns:
        [description]

    Raises:
        [description]
    """
    return time.time()
