"""sillo.cache.config — Domain-level cache configuration.

sillo.cache is intentionally decoupled from :class:`sillo.silloApp`. Instead of
wiring a backend through app config, you configure caching at the *domain*
level: instantiate a backend and register it as the default, then the
:func:`sillo.cache.cache` decorator uses that default unless you pass a
``backend=`` explicitly.

Example:
    ```python
    from sillo.cache import MemoryCache, configure_cache, cache

    configure_cache(MemoryCache(default_ttl=120))

    @cache(ttl=60)
    async def get_user(user_id: int):
        ...
    ```
"""

from __future__ import annotations

import threading
import typing
from dataclasses import dataclass, field
from typing import Any, Optional

from .backends import MemoryCache
from .base import BaseCache

# Module-level default backend. ``None`` means "use an implicit MemoryCache".
_DEFAULT: Optional[BaseCache] = None
_LOCK = threading.RLock()


def configure_cache(backend: BaseCache) -> None:
    """Set the process-wide default cache backend.

    After this call, ``@cache()`` with no ``backend=`` argument routes to the
    supplied backend. Calling it again swaps the default for all subsequently
    decorated functions (existing cached functions keep the backend they were
    created with).
    """
    global _DEFAULT
    with _LOCK:
        _DEFAULT = backend


def get_default_backend() -> BaseCache:
    """Return the current default backend, creating an implicit MemoryCache.

    The implicit backend is created lazily and memoized so that a simple app
    with no configuration still gets a working (process-local) cache.
    """
    global _DEFAULT
    with _LOCK:
        if _DEFAULT is None:
            _DEFAULT = MemoryCache()
        return _DEFAULT


def reset_cache_config() -> None:
    """Clear the default backend (primarily for tests)."""
    global _DEFAULT
    with _LOCK:
        _DEFAULT = None


@dataclass
class CacheSettings:
    """Reusable settings object for the :func:`cache` decorator.

    Pass an instance to several decorators to share TTL/namespace/version
    defaults without repeating arguments.
    """

    ttl: Optional[int] = None
    namespace: Optional[str] = None
    version: Optional[str] = None
    key_prefix: Optional[str] = None
    serializer: str = "json"
    tags: tuple = field(default_factory=tuple)
    sliding: bool = False


__all__ = [
    "configure_cache",
    "get_default_backend",
    "reset_cache_config",
    "CacheSettings",
]
