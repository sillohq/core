"""
sillo.security.ratelimit._middleware — the rate-limit middleware.

Wires a :class:`RateLimitConfig` to a resolved strategy + backend, evaluates
each request, and either lets it through (attaching ``X-RateLimit-*`` headers)
or short-circuits with a ``429`` response carrying ``Retry-After``.
"""

from __future__ import annotations

import typing
from typing import Any

from sillo.core.http import HttpContext, json
from sillo.middleware.base import BaseMiddleware

from .backends import RateLimitBackend, get_backend
from .config import RateLimitConfig
from .strategies import RateLimitStrategy, get_strategy

_HEADER_LIMIT = "X-RateLimit-Limit"
_HEADER_REMAINING = "X-RateLimit-Remaining"
_HEADER_RESET = "X-RateLimit-Reset"


class RateLimitMiddleware(BaseMiddleware):
    """Enforce request rate limits per client identity."""

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Init"""
        if config is not None and not isinstance(config, RateLimitConfig):
            raise TypeError("config must be a RateLimitConfig instance")
        self.config: RateLimitConfig = config or RateLimitConfig()
        self._strategy: RateLimitStrategy = get_strategy(self.config.strategy)
        self._backend: RateLimitBackend = get_backend(self.config.backend)
        self._last_result = None  # type: ignore[var-annotated]

    async def dispatch(
        self,
        ctx: HttpContext,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        """Count the hit, deny or continue, then stamp the limit headers."""
        request = ctx
        key = self.config._key_func(request)
        if key is None:
            return await call_next()

        full_key = f"{self.config.namespace}:{key}"
        try:
            result = await self._strategy.hit(
                self._backend,
                full_key,
                self.config.limit,
                self.config.window,
                cost=self.config.cost,
            )
        except Exception:
            if not self.config.fail_open:
                raise
            # Backend unavailable -> allow, but don't attach limit headers.
            return await call_next()

        self._last_result = result
        if not result.allowed:
            return self._deny(request, result)

        response = await call_next()
        self._set_limit_headers(response)
        return response

    def _set_limit_headers(self, response) -> None:
        """Write the ``X-RateLimit-*`` headers onto the outgoing response."""
        result = self._last_result
        if response is None or result is None or not self.config.include_headers:
            return
        response.set_header(_HEADER_LIMIT, str(result.limit), override=True)
        response.set_header(_HEADER_REMAINING, str(result.remaining), override=True)
        response.set_header(_HEADER_RESET, str(int(result.reset_at)), override=True)

    def _deny(self, ctx: HttpContext, result: Any):
        """Build the 429, or hand off to a configured ``on_exceed``."""
        if callable(self.config.on_exceed):
            return self.config.on_exceed(ctx, result)  # ty: ignore[call-top-callable]
        retry_after = max(int(result.retry_after), 1)
        return json(
            {
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Slow down and retry later.",
                "retry_after": retry_after,
            },
            status_code=429,
            headers={
                _HEADER_LIMIT: str(result.limit),
                _HEADER_REMAINING: "0",
                _HEADER_RESET: str(int(result.reset_at)),
                "Retry-After": str(retry_after),
            },
        )
