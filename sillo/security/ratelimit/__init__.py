"""
sillo.security.ratelimit — distributed-ready request rate limiting.

A self-contained limiter with pluggable algorithms (token bucket, fixed
window, sliding window) and pluggable backends (in-memory, Redis, sillo
Record). Use :class:`RateLimit` as a convenient wrapper around
:class:`RateLimitMiddleware`.
"""

from __future__ import annotations

import typing
from typing import Any, Optional

from ._middleware import RateLimitMiddleware
from .backends import (
    InMemoryBackend,
    RateLimitBackend,
    RateLimitResult,
    RecordBackend,
    RedisBackend,
    get_backend,
)
from .config import RateLimitConfig
from .strategies import (
    FixedWindowStrategy,
    RateLimitStrategy,
    SlidingWindowStrategy,
    TokenBucketStrategy,
    get_strategy,
)

__all__ = [
    "RateLimit",
    "RateLimitMiddleware",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitBackend",
    "InMemoryBackend",
    "RedisBackend",
    "RecordBackend",
    "get_backend",
    "RateLimitStrategy",
    "FixedWindowStrategy",
    "SlidingWindowStrategy",
    "TokenBucketStrategy",
    "get_strategy",
]


class RateLimit(RateLimitMiddleware):
    """Convenience subclass mirroring ``RateLimitConfig`` kwargs.

    Example::

        app.use(RateLimit(limit=100, window=60, backend="redis"))
    """

    def __init__(
        self,
        limit: int = 60,
        window: int = 60,
        strategy: Any = "token",
        backend: Any = "memory",
        key_func: Optional[Any] = None,
        namespace: str = "sillo_rl",
        cost: int = 1,
        include_headers: bool = True,
        fail_open: bool = True,
        on_exceed: Any = "deny",
        **kwargs: Any,
    ) -> None:
        """Init

            Args:
                limit: [description]
                window: [description]
                strategy: [description]
                backend: [description]
                key_func: [description]
                namespace: [description]
                cost: [description]
                include_headers: [description]
                fail_open: [description]
                on_exceed: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        config = RateLimitConfig(
            limit=limit,
            window=window,
            strategy=strategy,
            backend=backend,
            key_func=key_func,
            namespace=namespace,
            cost=cost,
            include_headers=include_headers,
            fail_open=fail_open,
            on_exceed=on_exceed,
        )
        super().__init__(config=config, **kwargs)
