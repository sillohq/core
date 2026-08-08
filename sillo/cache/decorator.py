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
from collections.abc import Callable
from typing import Any

from .base import _MISSING, BaseCache
from .config import CacheSettings, get_default_backend

_ = asyncio  # keep import referenced for lint clarity


def cache(
    *,
    backend: BaseCache | None = None,
    ttl: int | None = None,
    namespace: str | None = None,
    version: str | None = None,
    key_prefix: str | None = None,
    tags: tuple[str, ...] | None = None,
    sliding: bool = False,
    skip_cache_if: Callable[..., bool] | None = None,
    serializer: str | None = None,
    settings: CacheSettings | None = None,
) -> Callable[[Callable], Callable]:
    """Create a caching decorator for synchronous or asynchronous callables.

    Returns a decorator that wraps the target function or method so that its
    return value is stored in a cache backend and reused on subsequent calls
    with identical arguments. The decorator transparently handles both sync and
    async callables, and automatically excludes the ``self`` or ``cls``
    parameter from key generation for bound methods so that different instances
    share the same cache entries. Configuration precedence follows the order:
    explicit keyword arguments override values from a :class:`CacheSettings`
    object, which in turn override backend defaults.

    Args:
        backend: Explicit cache backend instance to use. When ``None``, the
            domain-level default set via :func:`sillo.cache.configure_cache`
            is used, or a lazily-created :class:`MemoryCache` if none was
            configured.
        ttl: Time-to-live in seconds for cached entries produced by this
            decorator. ``None`` defers to the backend's default TTL.
        namespace: Key namespace string that groups related cache entries
            together for bulk operations such as namespace-wide invalidation.
        version: Key version string. Bumping the version effectively invalidates
            all previously cached keys produced under the old version.
        key_prefix: Extra literal string prefixed to every generated cache key,
            useful for distinguishing different functional roles.
        tags: Tuple of invalidation tag strings attached to every cached entry
            produced by this decorator, enabling tag-based bulk invalidation.
        sliding: When ``True``, the TTL is refreshed on every cache read,
            implementing a sliding-window expiration policy instead of a
            fixed-duration expiration.
        skip_cache_if: Optional predicate callable receiving ``(*args, **kwargs)``
            and returning a boolean. When it returns ``True`` the wrapped
            function is executed and its result returned directly *without*
            reading from or writing to the cache.
        serializer: Serializer name override for this function's cached values.
            When ``None``, the backend's default serializer is used.
        settings: A :class:`CacheSettings` instance providing shared defaults
            for multiple decorators. Explicit keyword arguments take precedence.

    Returns:
        Callable[[Callable], Callable]: A decorator that wraps the original
            callable with caching behaviour. The wrapped callable exposes two
            extra attributes: ``cache_backend`` (the backend used) and
            ``invalidate`` (an async method to delete the cache entry for
            specific arguments).

    Raises:
        TypeError: If the wrapped target is not a callable.
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
        """Wrap *func* with caching behaviour, returning a transparent proxy.

        Inspects the target callable to determine whether it is a coroutine
        function and whether it is a bound method (by checking for ``self`` or
        ``cls`` as the first parameter). Selects the appropriate wrapper
        (``_async_wrapper`` or ``_sync_wrapper``) and attaches the
        ``cache_backend`` and ``invalidate`` helper attributes before returning.

        Args:
            func: The target callable to wrap with caching behaviour. Can be
                either a synchronous function or an asynchronous coroutine
                function, and may be a plain function or a bound method.

        Returns:
            Callable: A wrapper function that intercepts calls, checks the
                cache, and delegates to the original function on misses. The
                wrapper exposes ``cache_backend`` and ``invalidate`` attributes.

        Raises:
            TypeError: If *func* is not a callable object.
        """
        func_is_async = inspect.iscoroutinefunction(func)

        # Detect bound methods so self/cls is excluded from the key.
        _params = list(inspect.signature(func).parameters.values())
        _has_self = bool(_params) and _params[0].name in ("self", "cls")

        def build_key(args: tuple, kwargs: Any) -> str:
            """Construct a deterministic cache key for the given call arguments.

            Combines the optional key prefix, the function's fully-qualified
            module and qualified name, positional arguments (excluding ``self``
            or ``cls`` for bound methods), and sorted keyword arguments into a
            reproducible string via the backend's :meth:`make_key` method.
            Sorting of keyword arguments ensures that calls with the same
            parameters in different orders produce identical cache keys.

            Args:
                args: Positional arguments passed to the wrapped function.
                    For bound methods the first element (``self``/``cls``) is
                    stripped before key generation.
                kwargs: Keyword arguments passed to the wrapped function.
                    Items are sorted alphabetically by key name to guarantee
                    deterministic key generation regardless of call order.

            Returns:
                str: A unique, deterministic string key suitable for use with
                    the cache backend's ``get``, ``set``, and ``delete``
                    methods.

            Raises:
                No exceptions are raised under normal operation.
            """
            effective_backend = (
                backend if backend is not None else get_default_backend()
            )
            key_parts: list = []
            if key_prefix:
                key_parts.append(key_prefix)
            # Module + qualname gives global uniqueness across the codebase.
            key_parts.append(f"{func.__module__}.{func.__qualname__}")  # ty: ignore[unresolved-attribute]
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
            """Execute the wrapped function, handling both sync and async callables.

            For natively async functions the coroutine is awaited directly. For
            synchronous functions the call is dispatched to a thread-pool
            executor via :meth:`asyncio.loop.run_in_executor` so that the event
            loop is never blocked by potentially long-running CPU-bound or
            blocking I/O operations.

            Args:
                *args: Positional arguments forwarded to the wrapped function.
                **kwargs: Keyword arguments forwarded to the wrapped function.

            Returns:
                Any: The return value produced by the wrapped function, whether
                    it was executed as a native coroutine or via the executor.

            Raises:
                Exception: Any exception raised by the wrapped function is
                    propagated unchanged to the caller.
            """
            if func_is_async:
                return await func(*args, **kwargs)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, functools.partial(func, *args, **kwargs)
            )

        async def _lookup(*args: Any, **kwargs: Any) -> Any:
            """Look up a cached result or execute the function and store it.

            Core cache-or-compute logic: first evaluates the optional
            ``skip_cache_if`` predicate; if it returns ``True`` the function is
            executed without cache interaction. Otherwise the cache is checked
            for an existing entry. On a cache miss the function is executed via
            :func:`_execute` and the result is stored in the backend with the
            configured TTL, tags, and sliding-window settings before being
            returned to the caller.

            Args:
                *args: Positional arguments forwarded to the wrapped function
                    and used for cache key generation.
                **kwargs: Keyword arguments forwarded to the wrapped function
                    and used for cache key generation.

            Returns:
                Any: Either the previously cached result or the freshly
                    computed value from the wrapped function.

            Raises:
                Exception: Any exception raised by the wrapped function or the
                    cache backend is propagated unchanged to the caller.
            """
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
            """Async wrapper used when the wrapped function is a coroutine function.

            Provides a uniform ``async def`` interface so that callers can
            ``await`` the cached function exactly as they would the original.
            Delegates all cache-or-compute logic to :func:`_lookup` and
            preserves the original function's metadata via
            :func:`functools.wraps` for correct introspection and help output.

            Args:
                *args: Positional arguments forwarded to the cache lookup and,
                    on a miss, to the original wrapped function.
                **kwargs: Keyword arguments forwarded to the cache lookup and,
                    on a miss, to the original wrapped function.

            Returns:
                Any: The cached or freshly computed return value from the
                    wrapped function.

            Raises:
                Exception: Any exception raised during cache lookup or function
                    execution is propagated unchanged to the caller.
            """
            return await _lookup(*args, **kwargs)

        @functools.wraps(func)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Synchronous wrapper for non-async callables with caching.

            Bridges the synchronous calling convention to the internal async
            cache-or-compute pipeline. Detects whether an event loop is already
            running in the current thread: if so, it schedules the async lookup
            on a private event loop in a separate thread to avoid deadlocks;
            otherwise it creates or reuses an event loop and runs the lookup to
            completion via :meth:`loop.run_until_complete`. Preserves the
            original function's metadata via :func:`functools.wraps`.

            Args:
                *args: Positional arguments forwarded to the cache lookup and,
                    on a miss, to the original wrapped function.
                **kwargs: Keyword arguments forwarded to the cache lookup and,
                    on a miss, to the original wrapped function.

            Returns:
                Any: The cached or freshly computed return value from the
                    wrapped function, unwrapped from the async pipeline.

            Raises:
                RuntimeError: If no running event loop can be obtained or
                    created for the current thread.
                Exception: Any exception raised during cache lookup or function
                    execution is propagated unchanged to the caller.
            """
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
            """Invalidate the cached entry for the given call arguments.

            Constructs the same deterministic cache key that :func:`build_key`
            would produce for the supplied arguments and issues a ``delete``
            call against the effective cache backend. This allows callers to
            selectively evict a single cached result without flushing the
            entire cache or waiting for natural TTL expiration.

            Args:
                *args: Positional arguments that were originally passed to the
                    cached function, used to reconstruct the cache key.
                **kwargs: Keyword arguments that were originally passed to the
                    cached function, used to reconstruct the cache key.

            Returns:
                bool: ``True`` if a matching cache entry existed and was
                    successfully deleted, ``False`` if no entry was found for
                    the given arguments.

            Raises:
                Exception: Any exception raised by the cache backend during
                    the delete operation is propagated unchanged to the caller.
            """
            effective_backend = (
                backend if backend is not None else get_default_backend()
            )
            return await effective_backend.delete(build_key(args, kwargs))

        wrapper = _async_wrapper if func_is_async else _sync_wrapper
        wrapper.cache_backend = backend  # ty: ignore[invalid-assignment]
        wrapper.invalidate = _invalidate  # ty: ignore[invalid-assignment]
        return wrapper

    return decorator


__all__ = ["cache"]
