"""
RedisCache against a live server.

Skipped when no Redis is reachable. The memory backend is tested elsewhere;
these exist so the Redis code path is exercised for real rather than mocked,
because the bugs that matter here are serialization and TTL semantics that a
mock would paper over.

These were written against an older API and, because nothing ran them — no CI
job had a Redis server — they were never updated when it changed. They are now
written against the same surface ``tests/test_cache/test_memory_cache.py``
exercises: ``get`` returns ``_MISSING`` rather than ``None``, ``invalidate_tags``
takes varargs, and ``stats()`` is a call returning a ``CacheStats``.

They are also async tests rather than a synchronous ``asyncio.run`` per call.
A client opened in one loop cannot be used from the next, so the old shape
failed with "Future attached to a different loop" as soon as a test touched
the cache twice.
"""

import asyncio

import pytest

from sillo.cache.backends import RedisCache
from sillo.cache.base import _MISSING

from ..conftest import requires_redis

pytestmark = requires_redis


@pytest.fixture
async def cache(redis_url):
    c = RedisCache(url=redis_url, namespace="test")
    try:
        yield c
    finally:
        await c.close()


# ── round trip ───────────────────────────────────────────────────────────


async def test_set_and_get(cache):
    await cache.set("k", "v")
    assert await cache.get("k") == "v"


async def test_get_a_missing_key_reports_missing(cache):
    assert await cache.get("absent") is _MISSING


@pytest.mark.parametrize(
    "value",
    [
        "text",
        42,
        3.14,
        True,
        None,
        [1, 2, 3],
        {"nested": {"deep": [1, 2]}},
    ],
)
async def test_values_round_trip_with_their_type(cache, value):
    """None is in here deliberately: a stored None must not read back as a miss."""
    await cache.set("k", value)
    assert await cache.get("k") == value


async def test_overwriting_a_key(cache):
    await cache.set("k", "first")
    await cache.set("k", "second")
    assert await cache.get("k") == "second"


# ── existence and deletion ───────────────────────────────────────────────


async def test_exists(cache):
    await cache.set("k", "v")
    assert await cache.exists("k") is True


async def test_exists_for_a_missing_key(cache):
    assert await cache.exists("absent") is False


async def test_delete(cache):
    await cache.set("k", "v")
    assert await cache.delete("k") is True
    assert await cache.get("k") is _MISSING


async def test_deleting_a_missing_key_reports_false(cache):
    assert await cache.delete("never-existed") is False


async def test_clear_empties_the_cache(cache):
    """clear() filters by namespace, so it only sees keys make_key produced.

    Raw keys are stored verbatim — the backend namespaces nothing on the way
    in — so a namespaced cache cleared after ``set("a", 1)`` keeps "a". That is
    the same contract test_memory_cache.py::test_clear_namespace_only pins
    down, and the reason `test_clear_leaves_raw_keys_alone` below exists.
    """
    a, b = cache.make_key("a"), cache.make_key("b")
    await cache.set(a, 1)
    await cache.set(b, 2)
    await cache.clear()
    assert await cache.get(a) is _MISSING
    assert await cache.get(b) is _MISSING


async def test_clear_leaves_raw_keys_alone(cache):
    """A sharp edge, pinned so a change to it is deliberate.

    ``set`` does not namespace, ``clear`` filters by namespace, so a key
    written raw survives a clear with no error and no warning.
    """
    await cache.set("raw", 1)
    await cache.clear()
    assert await cache.get("raw") == 1


async def test_clear_without_a_namespace_removes_everything(redis_url):
    cache = RedisCache(url=redis_url)
    try:
        await cache.set("raw", 1)
        await cache.clear()
        assert await cache.get("raw") is _MISSING
    finally:
        await cache.close()


# ── expiry ───────────────────────────────────────────────────────────────


async def test_a_ttl_expires_the_entry(cache):
    await cache.set("k", "v", ttl=1)
    assert await cache.get("k") == "v"
    await asyncio.sleep(1.2)
    assert await cache.get("k") is _MISSING


async def test_no_ttl_persists(cache):
    await cache.set("k", "v")
    assert await cache.get("k") == "v"


async def test_touch_extends_the_lifetime(cache):
    await cache.set("k", "v", ttl=1)
    assert await cache.touch("k", ttl=30) is True
    await asyncio.sleep(1.2)
    assert await cache.get("k") == "v"


async def test_touching_a_missing_key_reports_false(cache):
    assert await cache.touch("absent", ttl=30) is False


# ── keys and namespacing ─────────────────────────────────────────────────


async def test_make_key_is_deterministic(cache):
    assert cache.make_key("a") == cache.make_key("a")


async def test_make_key_separates_distinct_keys(cache):
    assert cache.make_key("a") != cache.make_key("b")


async def test_namespaces_do_not_collide(redis_url):
    """Two caches on one server must not read each other's keys.

    Isolation comes from make_key, not from the backend: raw keys go to Redis
    verbatim, so ``one.set("k")`` and ``two.set("k")`` are the same key.
    """
    one = RedisCache(url=redis_url, namespace="one")
    two = RedisCache(url=redis_url, namespace="two")
    try:
        await one.set(one.make_key("k"), "from-one")
        await two.set(two.make_key("k"), "from-two")
        assert await one.get(one.make_key("k")) == "from-one"
        assert await two.get(two.make_key("k")) == "from-two"
    finally:
        await one.close()
        await two.close()


async def test_the_backend_reports_its_name(cache):
    assert isinstance(cache.name, str)


# ── statistics ───────────────────────────────────────────────────────────


async def test_hits_and_misses_are_counted(cache):
    await cache.set("k", "v")
    await cache.get("k")
    await cache.get("absent")
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1


async def test_reset_stats(cache):
    await cache.get("absent")
    cache.reset_stats()
    assert cache.stats().misses == 0


# ── tags ─────────────────────────────────────────────────────────────────


async def test_invalidate_tags(cache):
    await cache.set("k", "v", tags=["group-a"])
    assert await cache.invalidate_tags("group-a") >= 1
    assert await cache.get("k") is _MISSING


async def test_invalidate_tags_leaves_other_tags_alone(cache):
    await cache.set("a", 1, tags=["group-a"])
    await cache.set("b", 2, tags=["group-b"])
    await cache.invalidate_tags("group-a")
    assert await cache.get("a") is _MISSING
    assert await cache.get("b") == 2


async def test_invalidating_an_unused_tag_is_harmless(cache):
    assert await cache.invalidate_tags("never-used") == 0


# ── connection failure ───────────────────────────────────────────────────


async def test_an_unreachable_server_surfaces_an_error():
    """A dead Redis must not hang silently."""
    dead = RedisCache(url="redis://127.0.0.1:1/0")
    with pytest.raises(Exception):
        await dead.get("k")


# ── TTL must survive being read ──────────────────────────────────────────


async def test_reading_a_key_does_not_extend_its_life(redis_url):
    """get() used to touch every key it read.

    touch(key, None) resolves None to default_ttl, so an entry written with an
    explicit ttl=1 had its expiry pushed out to the backend default the moment
    anything read it. Nothing short-lived expired on time as long as it was
    being used.
    """
    cache = RedisCache(url=redis_url, default_ttl=60)
    try:
        await cache.set("k", 1, ttl=1)
        assert await cache.get("k") == 1
        await asyncio.sleep(1.3)
        assert await cache.get("k") is _MISSING
    finally:
        await cache.close()


async def test_a_sliding_value_reads_back_as_itself(redis_url):
    """A sliding entry is wrapped for storage; get() returned the wrapper."""
    cache = RedisCache(url=redis_url, default_ttl=60)
    try:
        await cache.set("k", {"real": "value"}, ttl=5, sliding=True)
        assert await cache.get("k") == {"real": "value"}
    finally:
        await cache.close()


async def test_a_sliding_value_is_kept_alive_by_reads(redis_url):
    cache = RedisCache(url=redis_url, default_ttl=60)
    try:
        await cache.set("k", "v", ttl=2, sliding=True)
        for _ in range(3):
            await asyncio.sleep(0.8)
            assert await cache.get("k") == "v"
    finally:
        await cache.close()
