"""Tests for sillo.cache.backends.MemoryCache (TTL, LRU, tags, versioning)."""

import asyncio
import time

import pytest

from sillo.cache.backends import MemoryCache
from sillo.cache.base import _MISSING


@pytest.fixture
def cache():
    return MemoryCache(namespace="test", default_ttl=100)


async def test_set_get_roundtrip(cache):
    await cache.set("k", {"v": 1})
    assert await cache.get("k") == {"v": 1}


async def test_get_missing_returns_missing(cache):
    assert await cache.get("nope") is _MISSING
    assert cache.stats().misses == 1
    assert cache.stats().hits == 0


async def test_exists(cache):
    await cache.set("k", 1)
    assert await cache.exists("k") is True
    assert await cache.exists("missing") is False


async def test_delete(cache):
    await cache.set("k", 1)
    assert await cache.delete("k") is True
    assert await cache.delete("k") is False
    assert await cache.exists("k") is False


async def test_absolute_ttl_expiry(cache):
    await cache.set("k", 1, ttl=1)
    assert await cache.get("k") == 1
    await asyncio.sleep(1.1)
    assert await cache.get("k") is _MISSING


async def test_sliding_ttl_refreshes(cache):
    # Sliding TTL of 1s; read before expiry extends it.
    await cache.set("k", 1, ttl=1, sliding=True)
    await asyncio.sleep(0.6)
    assert await cache.get("k") == 1  # read refreshes
    await asyncio.sleep(0.6)
    assert await cache.get("k") == 1  # still alive due to refresh
    await asyncio.sleep(1.1)
    assert await cache.get("k") is _MISSING


async def test_lru_eviction():
    c = MemoryCache(max_size=2)
    await c.set("a", 1)
    await c.set("b", 2)
    await c.set("c", 3)  # evicts "a" (oldest)
    assert await c.exists("a") is False
    assert await c.exists("b") is True
    assert await c.exists("c") is True
    assert c.stats().evictions == 1


async def test_lru_touch_recency():
    c = MemoryCache(max_size=2)
    await c.set("a", 1)
    await c.set("b", 2)
    await c.get("a")  # "a" becomes most-recent
    await c.set("c", 3)  # should evict "b" now
    assert await c.exists("a") is True
    assert await c.exists("b") is False


async def test_tag_invalidation(cache):
    await cache.set("u1", 1, tags=["user:1"])
    await cache.set("u2", 2, tags=["user:2"])
    await cache.set("u3", 3, tags=["user:1", "user:2"])
    removed = await cache.invalidate_tags("user:1")
    assert removed == 2
    assert await cache.exists("u1") is False
    assert await cache.exists("u2") is True
    assert await cache.exists("u3") is False


async def test_invalidate_tags_empty(cache):
    assert await cache.invalidate_tags() == 0


async def test_clear_namespace_only():
    ns1 = MemoryCache(namespace="a")
    ns2 = MemoryCache(namespace="b")
    # Keys created via make_key are namespaced, matching clear()'s filter.
    k1 = ns1.make_key("fn", 1)
    k2 = ns2.make_key("fn", 1)
    await ns1.set(k1, 1)
    await ns2.set(k2, 2)
    await ns1.clear()
    assert await ns1.exists(k1) is False
    assert await ns2.exists(k2) is True  # other namespace untouched


async def test_clear_without_a_namespace_flushes_everything():
    c = MemoryCache()
    await c.set("a", 1)
    await c.set("b", 2)
    await c.clear()
    assert await c.exists("a") is False
    assert await c.exists("b") is False


async def test_len_and_size():
    c = MemoryCache()
    assert len(c) == 0
    assert c.size() == 0
    await c.set("a", 1)
    await c.set("b", 2)
    assert len(c) == 2
    assert c.size() == 2


async def test_version_invalidation_via_keys(cache):
    v1 = MemoryCache(namespace="ns", default_ttl=100)
    v2 = MemoryCache(namespace="ns", default_ttl=100)
    k1 = v1.make_key("fn", 1, version="v1")
    k2 = v2.make_key("fn", 1, version="v2")
    assert k1 != k2
    await v1.set(k1, "old")
    await v2.set(k2, "new")
    assert await v1.get(k1) == "old"
    assert await v2.get(k2) == "new"


async def test_touch_extends_ttl(cache):
    await cache.set("k", 1, ttl=1)
    await asyncio.sleep(0.5)
    assert await cache.touch("k", ttl=5) is True
    await asyncio.sleep(0.6)
    assert await cache.get("k") == 1  # survived original 1s window


async def test_exists_evicts_an_expired_entry(cache):
    await cache.set("k", 1, ttl=1)
    await asyncio.sleep(1.1)
    assert await cache.exists("k") is False


async def test_touch_returns_false_for_an_expired_entry(cache):
    await cache.set("k", 1, ttl=1)
    await asyncio.sleep(1.1)
    assert await cache.touch("k", ttl=5) is False


async def test_touch_returns_false_for_a_missing_key(cache):
    assert await cache.touch("never-set", ttl=5) is False


async def test_stats_counts(cache):
    await cache.set("k", 1)
    await cache.get("k")
    await cache.get("missing")
    assert cache.stats().sets == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses >= 1


async def test_pickle_serializer():
    c = MemoryCache(serializer="pickle")
    obj = {"s": {1, 2, 3}}
    await c.set("k", obj)
    assert await c.get("k") == obj


async def test_close_clears(cache):
    await cache.set("k", 1)
    await cache.close()
    assert await cache.exists("k") is False
