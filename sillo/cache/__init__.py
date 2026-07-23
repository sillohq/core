"""sillo.cache — Advanced caching subsystem for sillo.

A pluggable, backend-agnostic cache with a function/method result decorator.

Quick start:
    ```python
    from sillo.cache import MemoryCache, configure_cache, cache

    configure_cache(MemoryCache(default_ttl=300))

    @cache(ttl=120, tags=["catalog"])
    async def get_product(product_id: int):
        ...
    ```

Backends: :class:`MemoryCache` (no deps) and :class:`RedisCache`
(``uv add "sillo[cache]"``). Configure at the domain level via
:func:`configure_cache`; the decorator falls back to that default unless you
pass ``backend=`` explicitly.
"""

from .backends import MemoryCache, RedisCache
from .base import (
    BaseCache,
    CacheError,
    CacheStats,
    SerializationError,
    build_key,
    tag_key,
)
from .config import (
    CacheSettings,
    configure_cache,
    get_default_backend,
    reset_cache_config,
)
from .decorator import cache

__all__ = [
    "BaseCache",
    "CacheError",
    "CacheStats",
    "SerializationError",
    "build_key",
    "tag_key",
    "MemoryCache",
    "RedisCache",
    "CacheSettings",
    "configure_cache",
    "get_default_backend",
    "reset_cache_config",
    "cache",
]
