from __future__ import annotations

import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from sillo.cache.base import BaseCache
    from sillo.http.client.middleware import HTTPMiddleware
    from sillo.http.client.retry import RetryStrategy


@dataclass
class HTTPClientConfig:
    """Configuration for the HTTP client.

    All duration values are in seconds.

    Attributes:
        base_url: Base URL prepended to all relative request URLs.
        default_timeout: Default timeout for requests (connect, read, write, pool).
        connect_timeout: Connection timeout specific override.
        read_timeout: Read timeout specific override.
        write_timeout: Write timeout specific override.
        pool_timeout: Pool timeout specific override.
        max_connections: Maximum number of connections in the connection pool.
        max_keepalive_connections: Maximum idle connections kept in the pool.
        verify_ssl: Whether to verify SSL certificates.
        trust_env: Whether to trust HTTP proxy settings from environment.
        follow_redirects: Whether to follow HTTP redirects automatically.
        max_redirects: Maximum number of redirects to follow.
        default_headers: Default headers sent with every request.
        default_auth: Default authentication as a tuple of (username, password).
        retry_strategy: Retry behaviour on transient failures.
        cache_backend: Cache backend instance for response caching.
        cache_ttl: Default TTL for cached responses (seconds).
        cache_key_prefix: Optional prefix for all cache keys.
        cache_tags: Optional list of cache invalidation tags.
        middlewares: Ordered list of middleware instances.
        raise_for_status: Whether to raise HTTPStatusError on non-2xx responses.
        user_agent: Custom User-Agent header value.
    """

    base_url: str = ""
    default_timeout: float = 30.0
    connect_timeout: float | None = None
    read_timeout: float | None = None
    write_timeout: float | None = None
    pool_timeout: float | None = None
    max_connections: int = 50
    max_keepalive_connections: int = 20
    verify_ssl: bool = True
    trust_env: bool = True
    follow_redirects: bool = True
    max_redirects: int = 20
    default_headers: dict[str, str] | None = None
    default_auth: tuple[str, str] | None = None
    retry_strategy: RetryStrategy | None = None
    cache_backend: BaseCache | None = None
    cache_ttl: int = 300
    cache_key_prefix: str | None = None
    cache_tags: list[str] | None = None
    middlewares: list[HTTPMiddleware] = field(default_factory=list)
    raise_for_status: bool = False
    user_agent: str | None = None

    def resolve_timeout(self) -> dict[str, float]:
        """Resolve the full timeout dictionary for httpx.

        Uses the specific timeout values when provided, falling back
        to ``default_timeout`` for any unset dimension.

        Returns:
            A dict with keys ``connect``, ``read``, ``write``, and ``pool``.
        """
        return {
            "connect": self.connect_timeout or self.default_timeout,
            "read": self.read_timeout or self.default_timeout,
            "write": self.write_timeout or self.default_timeout,
            "pool": self.pool_timeout or self.default_timeout,
        }


@dataclass
class HTTPClientStats:
    """Runtime statistics for an HTTPClient instance."""

    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    retries_total: int = 0

    @property
    def success_rate(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return (
            self.requests_total / self.requests_success
            if self.requests_success > 0
            else 0.0
        )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_failed": self.requests_failed,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "retries_total": self.retries_total,
            "success_rate": round(self.success_rate, 4),
        }


__all__ = [
    "HTTPClientConfig",
    "HTTPClientStats",
]
