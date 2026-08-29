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

from ..backends.base import RateLimitBackend, RateLimitResult


class RateLimitStrategy(abc.ABC):
    """Abstract base class for rate-limit algorithm implementations.

    Subclasses must implement ``hit()``, which encapsulates the core
    rate-limit decision logic (fixed-window, sliding-window, token-bucket,
    etc.). A strategy is stateless on its own — all state lives in the
    ``RateLimitBackend`` passed to ``hit()``.

    The base class provides no custom ``__init__``; subclasses are free
    to accept their own configuration parameters.
    """

    @abc.abstractmethod
    async def hit(
        self,
        backend: RateLimitBackend,
        key: str,
        limit: int,
        window: int,
        cost: int = 1,
        now: float | None = None,
    ) -> RateLimitResult:
        """Evaluate one request against the rate-limit state and return the decision.

        Loads the current state for *key* from the *backend*, decides
        whether the request is allowed based on the algorithm, persists
        any updated state, and returns a ``RateLimitResult`` with the
        verdict, remaining count, and reset time.

        Args:
            backend: The storage backend holding per-key counters.
            key: Unique identifier for the entity being rate-limited
                (typically an IP or user ID).
            limit: Maximum number of requests allowed within the window.
            window: Time window in seconds.
            cost: Request cost in tokens (default 1). Set >1 for heavy
                endpoints.
            now: Current timestamp as ``time.time()``. Passed explicitly
                for testability — defaults to ``time.time()`` when
                ``None``.

        Returns:
            A ``RateLimitResult`` with ``allowed``, ``remaining``,
            ``reset_at``, and ``retry_at`` fields.
        """
        raise NotImplementedError
