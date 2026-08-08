"""
sillo.security — Security utilities for sillo applications.

Provides CSRF protection, CORS middleware, security header management, and
request rate limiting. All security-related features are consolidated here
for a cohesive security API.

Usage::

    from sillo.security import CSRFConfig, CSRFMiddleware
    from sillo.security import CorsConfig, CORSMiddleware
    from sillo.security import Shield
    from sillo.security import RateLimit, RateLimitConfig

    app = silloApp()
    app.use(CSRFMiddleware(config=CSRFConfig(enabled=True, secret_key="...")))
    app.use(CORSMiddleware(config=CorsConfig(allow_origins=["*"])))
    app.use(Shield())
    app.use(RateLimit(limit=100, window=60))
"""

from sillo._internals.lazy import deferred

from .cors import CorsConfig, CORSMiddleware
from .csrf import CSRFConfig, CSRFMiddleware
from .ratelimit import (
    InMemoryBackend,
    RateLimit,
    RateLimitBackend,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitResult,
)
from .shield import Shield

__all__ = [
    "CORSMiddleware",
    "CSRFConfig",
    "CSRFMiddleware",
    "CorsConfig",
    "InMemoryBackend",
    "RateLimit",
    "RateLimitBackend",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RateLimitResult",
    "RecordBackend",
    "RedisBackend",
    "Shield",
]


#: The Record backend defines a Tortoise model and the Redis one needs redis.
#: This package is reached from the middleware package, which an application
#: imports unconditionally, so neither may be imported eagerly.
__getattr__ = deferred(
    __name__, {"RecordBackend": ".ratelimit", "RedisBackend": ".ratelimit"}
)
