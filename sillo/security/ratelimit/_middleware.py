"""
sillo.security.ratelimit._middleware — the rate-limit middleware.

Wires a :class:`RateLimitConfig` to a resolved strategy + backend, evaluates
each request, and either lets it through (attaching ``X-RateLimit-*`` headers)
or short-circuits with a ``429`` response carrying ``Retry-After``.
"""

from __future__ import annotations

import typing
from typing import Any, Optional

from typing_extensions import Doc

from sillo.core.http import Request, Response
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
        config: Optional[RateLimitConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Init

        Args:
            config: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if config is not None and not isinstance(config, RateLimitConfig):
            raise TypeError("config must be a RateLimitConfig instance")
        self.config: RateLimitConfig = config or RateLimitConfig()
        self._strategy: RateLimitStrategy = get_strategy(self.config.strategy)
        self._backend: RateLimitBackend = get_backend(self.config.backend)
        self._last_result = None  # type: ignore[var-annotated]

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        """Process Request

        Args:
            request: [description]
            response: [description]
            call_next: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
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
            return self._deny(request, response, result)
        return await call_next()

    async def process_response(self, request: Request, response: Response):
        """Process Response

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        result = self._last_result
        if result is None or not self.config.include_headers:
            return
        response.set_header(_HEADER_LIMIT, str(result.limit), overide=True)
        response.set_header(_HEADER_REMAINING, str(result.remaining), overide=True)
        response.set_header(_HEADER_RESET, str(int(result.reset_at)), overide=True)

    def _deny(self, request: Request, response: Response, result: Any):
        """Deny

        Args:
            request: [description]
            response: [description]
            result: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if callable(self.config.on_exceed):
            return self.config.on_exceed(request, response, result)  # ty: ignore[call-top-callable, too-many-positional-arguments]
        retry_after = max(int(result.retry_after), 1)
        return response.json(
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
