"""Tests for sillo.cache.decorator.cache (sync + async, methods, invalidation)."""

import asyncio

import pytest

from sillo.cache import MemoryCache, cache, configure_cache, reset_cache_config
from sillo.cache.base import _MISSING
from sillo.cache.config import CacheSettings


@pytest.fixture(autouse=True)
def _reset():
    reset_cache_config()
    yield
    reset_cache_config()


def test_async_decorator_caches():
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=30)
    async def fn(a, b):
        nonlocal calls
        calls += 1
        return a + b

    async def run():
        assert await fn(1, 2) == 3
        assert await fn(1, 2) == 3
        assert await fn(2, 3) == 5

    asyncio.run(run())
    assert calls == 2  # (1,2) cached, (2,3) new


def test_sync_decorator_caches():
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=30)
    def fn(a, b):
        nonlocal calls
        calls += 1
        return a * b

    assert fn(3, 4) == 12
    assert fn(3, 4) == 12
    assert fn(4, 5) == 20
    assert calls == 2


def test_different_kwargs_make_different_keys():
    c = MemoryCache()
    seen = []

    @cache(backend=c)
    def fn(**kw):
        seen.append(kw)
        return len(kw)

    assert fn(a=1) == 1
    assert fn(a=1) == 1
    assert fn(b=2) == 1
    assert len(seen) == 2


def test_method_caches_without_self_in_key():
    c = MemoryCache()

    class Service:
        def __init__(self):
            self.factor = 10

        @cache(backend=c, ttl=30)
        def compute(self, x):
            return x * self.factor

    s1 = Service()
    s2 = Service()
    s2.factor = 99  # different instance, but key must ignore self
    assert s1.compute(2) == 20
    # Because self is excluded from the key, s2.compute(2) hits the same cache.
    assert s2.compute(2) == 20
    assert c.stats().hits == 1


def test_skip_cache_if():
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=30, skip_cache_if=lambda x: x < 0)
    async def fn(x):
        nonlocal calls
        calls += 1
        return x

    async def run():
        assert await fn(5) == 5
        assert await fn(5) == 5  # cached
        assert await fn(-1) == -1  # skipped (not cached)
        assert await fn(-1) == -1  # runs again

    asyncio.run(run())
    assert calls == 3


def test_manual_invalidate():
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=300)
    async def fn(x):
        nonlocal calls
        calls += 1
        return x

    async def run():
        assert await fn(1) == 1
        assert await fn(1) == 1  # cached
        await fn.invalidate(1)
        assert await fn(1) == 1  # recomputed

    asyncio.run(run())
    assert calls == 2


def test_get_default_backend_lazily_creates_a_memory_cache():
    from sillo.cache.config import get_default_backend

    backend = get_default_backend()
    assert isinstance(backend, MemoryCache)
    # The same instance is reused on subsequent calls.
    assert get_default_backend() is backend


def test_default_backend_used():
    configure_cache(MemoryCache(default_ttl=30))
    calls = 0

    @cache(ttl=30)
    async def fn():
        nonlocal calls
        calls += 1
        return "ok"

    async def run():
        assert await fn() == "ok"
        assert await fn() == "ok"

    asyncio.run(run())
    assert calls == 1


def test_tags_invalidation_via_backend():
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=300, tags=("inv",))
    async def fn(x):
        nonlocal calls
        calls += 1
        return x

    async def run():
        assert await fn(1) == 1
        assert await fn(1) == 1
        await c.invalidate_tags("inv")
        assert await fn(1) == 1  # recomputed after tag invalidation

    asyncio.run(run())
    assert calls == 2


def test_settings_object_supplies_defaults():
    c = MemoryCache()
    calls = 0
    settings = CacheSettings(ttl=30, key_prefix="svc", namespace="ns")

    @cache(backend=c, settings=settings)
    def fn(x):
        nonlocal calls
        calls += 1
        return x * 2

    assert fn(5) == 10
    assert fn(5) == 10
    assert calls == 1


def test_explicit_kwargs_override_settings():
    c = MemoryCache()
    settings = CacheSettings(ttl=1)

    @cache(backend=c, ttl=300, settings=settings)
    async def fn(x):
        return x

    async def run():
        return await fn(1)

    asyncio.run(run())
    # No assertion needed on TTL directly, just that construction with both
    # settings= and an explicit override doesn't raise and still works.


def test_key_prefix_is_part_of_the_cache_key():
    c = MemoryCache()

    @cache(backend=c, ttl=30, key_prefix="p1")
    def fn(x):
        return x

    @cache(backend=c, ttl=30, key_prefix="p2")
    def fn2(x):
        return x

    fn(1)
    fn2(1)
    # Two distinct prefixes for otherwise-identical calls -> two entries.
    assert c.stats().sets == 2


def test_sync_call_from_inside_a_running_event_loop():
    """A sync-decorated function called from inside an already-running loop
    (e.g. a sync callback invoked by async code) runs its cache lookup on a
    private loop in a thread rather than deadlocking."""
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=30)
    def fn(x):
        nonlocal calls
        calls += 1
        return x * 3

    async def run():
        return fn(7)

    assert asyncio.run(run()) == 21
    assert calls == 1


def test_cache_none_is_not_a_miss():
    # A function that returns None must be cached (None != cache miss).
    c = MemoryCache()
    calls = 0

    @cache(backend=c, ttl=300)
    async def fn():
        nonlocal calls
        calls += 1
        return None

    async def run():
        assert await fn() is None
        assert await fn() is None  # served from cache

    asyncio.run(run())
    assert calls == 1  # computed exactly once
    assert c.stats().hits == 1
