"""sillo.cache.config — Domain-level cache configuration.

sillo.cache is intentionally decoupled from :class:`sillo.SilloApp`. Instead of
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
from dataclasses import dataclass, field

from .backends import MemoryCache
from .base import BaseCache

# Module-level default backend. ``None`` means "use an implicit MemoryCache".
_DEFAULT: BaseCache | None = None
_LOCK = threading.RLock()


def configure_cache(backend: BaseCache) -> None:
    """Set the process-wide default cache backend for all cache operations.

    Establishes the given backend as the global default used by the ``@cache()``
    decorator whenever no explicit ``backend=`` argument is supplied at decoration
    time. The configuration is protected by a reentrant lock so that concurrent
    callers from multiple threads cannot observe a partially-updated state.
    Subsequent calls replace the previous default; already-decorated functions
    retain the backend reference they captured at decoration time.

    Args:
        backend: A fully-initialised :class:`~sillo.cache.base.BaseCache`
            instance (e.g. ``MemoryCache`` or ``RedisCache``) to serve as the
            process-wide default for all cache decorator operations.

    Returns:
        None. The function operates purely via a module-level side effect.

    Raises:
        TypeError: If *backend* is not an instance of
            :class:`~sillo.cache.base.BaseCache`.
    """
    global _DEFAULT
    with _LOCK:
        _DEFAULT = backend


def get_default_backend() -> BaseCache:
    """Return the current default cache backend, creating one if necessary.

    If :func:`configure_cache` has been called, the configured backend is
    returned directly. Otherwise, an implicit :class:`MemoryCache` instance is
    created lazily on first access and memoized so that all subsequent calls
    return the same object without additional allocation. The entire check-and-
    create sequence is guarded by a reentrant lock to ensure thread safety.

    Args:
        None. This function takes no parameters.

    Returns:
        BaseCache: The active default cache backend. Either the backend
            previously registered via :func:`configure_cache`, or a freshly
            created :class:`~sillo.cache.backends.MemoryCache` instance if no
            explicit configuration has been performed yet.

    Raises:
        No exceptions are raised under normal operation.
    """
    global _DEFAULT
    with _LOCK:
        if _DEFAULT is None:
            _DEFAULT = MemoryCache()
        return _DEFAULT


def reset_cache_config() -> None:
    """Clear the process-wide default cache backend, resetting to unconfigured.

    Sets the module-level default backend reference back to ``None`` so that the
    next call to :func:`get_default_backend` will lazily create a fresh implicit
    :class:`MemoryCache`. This function is primarily intended for use in test
    suites that need to isolate cache state between test cases and guarantee a
    clean starting environment. The operation is protected by a reentrant lock.

    Args:
        None. This function takes no parameters.

    Returns:
        None. The function operates purely via a module-level side effect.

    Raises:
        No exceptions are raised under normal operation.
    """
    global _DEFAULT
    with _LOCK:
        _DEFAULT = None


@dataclass
class CacheSettings:
    """Reusable settings object for the :func:`cache` decorator.

    Encapsulates the most common cache configuration parameters into a single
    dataclass instance that can be shared across multiple ``@cache()``
    decorators. This avoids repeating identical keyword arguments at every call
    site and provides a single point of maintenance for tuning cache behaviour
    across related functions. Pass an instance via the ``settings=`` keyword
    argument to the :func:`cache` decorator; explicit keyword arguments always
    take precedence over values supplied through this object.

    Args:
        ttl: Default time-to-live in seconds for cached entries. When ``None``,
            the backend's own default TTL is used instead.
        namespace: Default key namespace for grouping related cache entries
            together, enabling bulk invalidation operations.
        version: Default key version string. Bumping the version effectively
            invalidates all keys produced under the previous version.
        key_prefix: Extra literal string prefixed to every generated cache key,
            useful for distinguishing different functional roles.
        serializer: Name of the serializer to use for encoding and decoding
            cached values (default ``"json"``).
        tags: Tuple of string tags attached to every cached entry for
            tag-based invalidation without knowing specific keys.
        sliding: When ``True``, the TTL is refreshed on every cache read,
            implementing a sliding-window expiration policy.

    Returns:
        None. This is a dataclass and does not return a value on instantiation.

    Raises:
        No exceptions are raised during normal instantiation.
    """

    ttl: int | None = None
    namespace: str | None = None
    version: str | None = None
    key_prefix: str | None = None
    serializer: str = "json"
    tags: tuple = field(default_factory=tuple)
    sliding: bool = False


__all__ = [
    "CacheSettings",
    "configure_cache",
    "get_default_backend",
    "reset_cache_config",
]
