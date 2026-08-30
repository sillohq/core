"""
sillo.security.ratelimit.config — configuration for the rate-limit middleware.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sillo.core.http import HttpContext


class RateLimitConfig:
    """Configuration object for :class:`RateLimitMiddleware`.

    Args:
        limit: Maximum requests allowed per ``window``.
        window: Time window in seconds.
        strategy: ``"token"`` (default), ``"fixed"``, ``"sliding"``, or a
            :class:`RateLimitStrategy` instance.
        backend: ``"memory"`` (default), ``"redis"``, ``"record"``, or a
            :class:`RateLimitBackend` instance.
        key_func: Callable mapping a :class:`HttpContext` to a string identity
            (default: client IP address). Return ``None`` to skip limiting.
        namespace: Prefix for backend keys, to avoid collisions.
        cost: Tokens consumed per request (default 1; raise for heavy routes).
        include_headers: Emit ``X-RateLimit-*`` headers (default ``True``).
        fail_open: If the backend raises, allow the request (default ``True``).
        on_exceed: ``"deny"`` (default, returns ``429``) or a callable that
            receives ``(ctx, result)`` and returns a response.
    """

    def __init__(
        self,
        limit: int = 60,
        window: int = 60,
        strategy: str | Any = "token",
        backend: str | Any = "memory",
        key_func: Callable[[HttpContext], str | None] | None = None,
        namespace: str = "sillo_rl",
        cost: int = 1,
        include_headers: bool = True,
        fail_open: bool = True,
        on_exceed: str | Callable[[HttpContext, Any], Any] = "deny",
    ) -> None:
        """Init"""
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        if window <= 0:
            raise ValueError("window must be a positive integer")
        if cost <= 0:
            raise ValueError("cost must be a positive integer")

        self.limit = limit
        self.window = window
        self.strategy = strategy
        self.backend = backend
        self.namespace = namespace
        self.cost = cost
        self.include_headers = include_headers
        self.fail_open = fail_open
        self.on_exceed = on_exceed
        self._key_func = key_func or self._default_key

    @staticmethod
    def _default_key(ctx: HttpContext) -> str | None:
        """Default Key"""
        client = ctx.client
        if client is not None:
            return client[0]
        return ctx.headers.get("x-forwarded-for")
