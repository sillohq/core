from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256

if typing.TYPE_CHECKING:
    from typing import Any, Optional

    from httpx import Request, Response

    from sillo.cache.base import BaseCache
    from sillo.http.client.models import CachedResponse


class CachePolicy(str, Enum):
    """Available cache policies for HTTP responses."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"


@dataclass
class CacheConfig:
    """Per-request or per-client cache configuration.

    Attributes:
        policy: The cache policy to apply.
        ttl: Time-to-live in seconds for cached responses.
        key_prefix: Optional prefix for all cache keys under this config.
        tags: Optional list of invalidation tags for group-based purging.
        status_codes: Set of HTTP status codes eligible for caching.
        methods: Set of HTTP methods eligible for caching. Defaults to GET only.
        include_query: When True, query parameters are included in the cache key.
        include_headers: When True, select headers are included in the cache key.
        cache_key_headers: Specific headers to include in the cache key.
    """

    policy: CachePolicy = CachePolicy.ENABLED
    ttl: int = 300
    key_prefix: Optional[str] = None
    tags: Optional[list[str]] = None
    status_codes: set[int] = frozenset({200})
    methods: set[str] = frozenset({"GET"})
    include_query: bool = True
    include_headers: bool = False
    cache_key_headers: Optional[list[str]] = None

    def should_cache_response(self, response: Response) -> bool:
        if self.policy == CachePolicy.DISABLED or self.policy == CachePolicy.READ_ONLY:
            return False
        method = response.request.method if response.request else "GET"
        return (
            response.status_code in self.status_codes
            and method.upper() in self.methods
        )

    def should_read_from_cache(self, request: Request) -> bool:
        if self.policy == CachePolicy.DISABLED or self.policy == CachePolicy.WRITE_ONLY:
            return False
        return request.method.upper() in self.methods


class CacheKeyBuilder:
    """Builds deterministic cache keys from HTTP request attributes."""

    @staticmethod
    def build(
        request: Request,
        prefix: Optional[str] = None,
        include_query: bool = True,
        include_headers: bool = False,
        cache_key_headers: Optional[list[str]] = None,
    ) -> str:
        """Build a cache key from a request."""
        parts: list[str] = [
            request.method.upper(),
            str(request.url),
        ]

        if include_query and request.url.query:
            parts.append(request.url.query.decode("utf-8", errors="replace"))

        if include_headers and cache_key_headers:
            for header_name in cache_key_headers:
                value = request.headers.get(header_name)
                if value:
                    parts.append(f"{header_name.lower()}:{value}")

        if request.content:
            raw = request.content
            if isinstance(raw, bytes):
                parts.append(sha256(raw).hexdigest()[:16])

        key = sha256("|".join(parts).encode("utf-8")).hexdigest()
        if prefix:
            key = f"{prefix}:{key}"
        return key


class HTTPCache:
    """Integrates the sillo.cache subsystem with the HTTP client.

    Wraps a BaseCache backend and provides cache-first request
    resolution with automatic serialization of CachedResponse objects.
    """

    def __init__(
        self,
        backend: BaseCache,
        config: Optional[CacheConfig] = None,
    ) -> None:
        self._backend = backend
        self._config = config or CacheConfig()

    @property
    def backend(self) -> BaseCache:
        return self._backend

    @property
    def config(self) -> CacheConfig:
        return self._config

    @config.setter
    def config(self, value: CacheConfig) -> None:
        self._config = value

    async def get(self, request: Request) -> Any:
        """Look up a cached response for the given request."""
        from sillo.cache.base import _MISSING

        key = CacheKeyBuilder.build(
            request,
            prefix=self._config.key_prefix,
            include_query=self._config.include_query,
            include_headers=self._config.include_headers,
            cache_key_headers=self._config.cache_key_headers,
        )

        raw = await self._backend.get(key)
        if raw is _MISSING:
            return _MISSING

        if isinstance(raw, dict):
            from sillo.http.client.models import CachedResponse

            return CachedResponse.from_json_dict(raw)
        return raw

    async def set(
        self,
        request: Request,
        response: Response,
        ttl: Optional[int] = None,
    ) -> None:
        """Store a response in the cache."""
        from sillo.http.client.models import CachedResponse

        effective_ttl = ttl if ttl is not None else self._config.ttl
        cached = CachedResponse.from_httpx_response(response, ttl=effective_ttl)

        key = CacheKeyBuilder.build(
            request,
            prefix=self._config.key_prefix,
            include_query=self._config.include_query,
            include_headers=self._config.include_headers,
            cache_key_headers=self._config.cache_key_headers,
        )

        await self._backend.set(
            key,
            cached.to_json_dict(),
            ttl=effective_ttl,
            tags=self._config.tags,
        )

    async def invalidate(self, request: Request) -> bool:
        """Delete a cached response for the given request."""
        key = CacheKeyBuilder.build(
            request,
            prefix=self._config.key_prefix,
            include_query=self._config.include_query,
            include_headers=self._config.include_headers,
            cache_key_headers=self._config.cache_key_headers,
        )
        return await self._backend.delete(key)

    async def invalidate_tags(self, *tags: str) -> int:
        return await self._backend.invalidate_tags(*tags)

    async def clear(self) -> None:
        await self._backend.clear()


__all__ = [
    "CachePolicy",
    "CacheConfig",
    "CacheKeyBuilder",
    "HTTPCache",
]
