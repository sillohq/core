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

from .cors import CORSMiddleware, CorsConfig
from .csrf import CSRFConfig, CSRFMiddleware
from .ratelimit import (
    InMemoryBackend,
    RateLimit,
    RateLimitBackend,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitResult,
    RecordBackend,
    RedisBackend,
)
from .shield import Shield

__all__ = [
    "CSRFConfig",
    "CSRFMiddleware",
    "CorsConfig",
    "CORSMiddleware",
    "Shield",
    "RateLimit",
    "RateLimitMiddleware",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitBackend",
    "InMemoryBackend",
    "RedisBackend",
    "RecordBackend",
]
