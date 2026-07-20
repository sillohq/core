"""sillo.cache.decorator — ``@cache()`` function/method result caching.

The decorator works on both sync and async callables, and on bound methods
(``self``/``cls`` is excluded from the key by default so instances share a
cache). It is backend-agnostic: pass ``backend=`` or rely on the domain default
set via :func:`sillo.cache.configure_cache`.

Example:
    ```python
    from sillo.cache import cache, MemoryCache, configure_cache

    configure_cache(MemoryCache(default_ttl=300))

    @cache(ttl=120, tags=["catalog"])
    async def get_product(product_id: int):
        return await db.products.get(product_id)

    @cache(namespace="users", version="v2")
    def expensive_sync(user_id: int):
        return compute(user_id)
    ```
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import typing
from typing import Any, Callable, Optional, Tuple

from .base import BaseCache, _MISSING
from .config import CacheSettings, get_default_backend

_ = asyncio  # keep import referenced for lint clarity


def cache(
    *,
    backend: Optional[BaseCache] = None,
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    version: Optional[str] = None,
    key_prefix: Optional[str] = None,
    tags: Optional[Tuple[str, ...]] = None,
    sliding: bool = False,
    skip_cache_if: Optional[Callable[..., bool]] = None,
    serializer: Optional[str] = None,
    settings: Optional[CacheSettings] = None,
) -> Callable[[Callable], Callable]:
    """Cache the result of a function or method.

    Args:
        backend: Explicit cache backend. Falls back to the domain default.
        ttl: Time-to-live in seconds for cached entries.
        namespace: Key namespace (groups keys for bulk operations).
        version: Key version; bumping it invalidates all keys at once.
        key_prefix: Extra literal prefixed into the key (e.g. function role).
        tags: Tuple of invalidation tags attached to every cached entry.
        sliding: Use sliding TTL (refreshed on each read).
        skip_cache_if: Predicate ``(*args, **kwargs) -> bool``; when it returns
            ``True`` the call is executed and returned WITHOUT caching.
        serializer: Override backend serializer for this function's values.
        settings: A :class:`CacheSettings` instance providing shared defaults.

    Returns:
        A decorator that wraps the original callable with caching.
    """
    # Resolve settings precedence: explicit kwargs > settings object > default.
    if settings is not None:
        ttl = ttl if ttl is not None else settings.ttl
        namespace = namespace if namespace is not None else settings.namespace
        version = version if version is not None else settings.version
        key_prefix = key_prefix if key_prefix is not None else settings.key_prefix
        tags = tags if tags is not None else settings.tags
        sliding = sliding or settings.sliding
        serializer = serializer if serializer is not None else settings.serializer

    def decorator(func: Callable) -> Callable:
        func_is_async = inspect.iscoroutinefunction(func)

        # Detect bound methods so self/cls is excluded from the key.
        _params = list(inspect.signature(func).parameters.values())
        _has_self = bool(_params) and _params[0].name in ("self", "cls")

        def build_key(args: Tuple, kwargs: Any) -> str:
            effective_backend = backend if backend is not None else get_default_backend()
            key_parts: list = []
            if key_prefix:
                key_parts.append(key_prefix)
            # Module + qualname gives global uniqueness across the codebase.
            key_parts.append(f"{func.__module__}.{func.__qualname__}")
            call_args = list(args)
            if _has_self:
                call_args = call_args[1:]  # drop bound instance/class
            key_parts.append(call_args)
            # Sort kwargs for a deterministic key regardless of call order.
            key_parts.append(sorted(kwargs.items()))
            return effective_backend.make_key(
                *key_parts, namespace=namespace, version=version
            )

        async def _execute(*args: Any, **kwargs: Any) -> Any:
            if func_is_async:
                return await func(*args, **kwargs)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, functools.partial(func, *args, **kwargs)
            )

        async def _lookup(*args: Any, **kwargs: Any) -> Any:
            cache_backend = backend if backend is not None else get_default_backend()
            cache_key = build_key(args, kwargs)
            if skip_cache_if is not None and skip_cache_if(*args, **kwargs):
                return await _execute(*args, **kwargs)
            cached = await cache_backend.get(cache_key)
            if cached is not _MISSING:
                return cached
            result = await _execute(*args, **kwargs)
            await cache_backend.set(
                cache_key, result, ttl=ttl, tags=tags, sliding=sliding
            )
            return result

        @functools.wraps(func)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _lookup(*args, **kwargs)

        @functools.wraps(func)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                loop = asyncio.get_event_loop()
                running = loop.is_running()
            except RuntimeError:
                loop = None
                running = False
            if running:
                # Inside a running loop: run on a private loop in a thread.
                fut = asyncio.run_coroutine_threadsafe(
                    _lookup(*args, **kwargs), asyncio.new_event_loop()
                )
                return fut.result()
            if loop is None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(_lookup(*args, **kwargs))

        async def _invalidate(*args: Any, **kwargs: Any) -> bool:
            effective_backend = backend if backend is not None else get_default_backend()
            return await effective_backend.delete(build_key(args, kwargs))

        wrapper = _async_wrapper if func_is_async else _sync_wrapper
        wrapper.cache_backend = backend  # type: ignore[attr-defined]
        wrapper.invalidate = _invalidate  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = ["cache"]
