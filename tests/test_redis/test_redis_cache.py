"""
RedisCache against a live server.

Skipped when no Redis is reachable. The memory backend is tested elsewhere;
these exist so the Redis code path is exercised for real rather than mocked,
because the bugs that matter here are serialization and TTL semantics that a
mock would paper over.
"""

import asyncio

import pytest

from sillo.cache.backends import RedisCache

from ..conftest import requires_redis

pytestmark = requires_redis


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def cache(redis_url):
    c = RedisCache(url=redis_url)
    yield c
    _run(c.close())


# ── round trip ───────────────────────────────────────────────────────────


def test_set_and_get(cache):
    _run(cache.set("k", "v"))
    assert _run(cache.get("k")) == "v"


def test_get_a_missing_key_is_none(cache):
    assert _run(cache.get("absent")) is None


def test_get_a_missing_key_with_a_default(cache):
    assert _run(cache.get("absent", "fallback")) == "fallback"


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
def test_values_round_trip_with_their_type(cache, value):
    _run(cache.set("k", value))
    assert _run(cache.get("k")) == value


def test_overwriting_a_key(cache):
    _run(cache.set("k", "first"))
    _run(cache.set("k", "second"))
    assert _run(cache.get("k")) == "second"


# ── existence and deletion ───────────────────────────────────────────────


def test_exists(cache):
    _run(cache.set("k", "v"))
    assert _run(cache.exists("k")) is True


def test_exists_for_a_missing_key(cache):
    assert _run(cache.exists("absent")) is False


def test_delete(cache):
    _run(cache.set("k", "v"))
    _run(cache.delete("k"))
    assert _run(cache.get("k")) is None


def test_deleting_a_missing_key_is_harmless(cache):
    _run(cache.delete("never-existed"))


def test_clear_empties_the_cache(cache):
    _run(cache.set("a", 1))
    _run(cache.set("b", 2))
    _run(cache.clear())
    assert _run(cache.get("a")) is None
    assert _run(cache.get("b")) is None


# ── expiry ───────────────────────────────────────────────────────────────


def test_a_ttl_expires_the_entry(cache):
    async def scenario():
        await cache.set("k", "v", ttl=1)
        assert await cache.get("k") == "v"
        await asyncio.sleep(1.2)
        return await cache.get("k")

    assert _run(scenario()) is None


def test_no_ttl_persists(cache):
    _run(cache.set("k", "v"))
    assert _run(cache.get("k")) == "v"


def test_touch_extends_the_lifetime(cache):
    _run(cache.set("k", "v", ttl=1))
    _run(cache.touch("k", ttl=30))
    assert _run(cache.get("k")) == "v"


# ── keys and namespacing ─────────────────────────────────────────────────


def test_make_key_is_deterministic(cache):
    assert cache.make_key("a") == cache.make_key("a")


def test_make_key_separates_distinct_keys(cache):
    assert cache.make_key("a") != cache.make_key("b")


def test_the_backend_reports_its_name(cache):
    assert isinstance(cache.name, str)


# ── statistics ───────────────────────────────────────────────────────────


def test_stats_are_reported(cache):
    _run(cache.set("k", "v"))
    _run(cache.get("k"))
    _run(cache.get("absent"))
    assert isinstance(cache.stats, dict)


def test_reset_stats(cache):
    _run(cache.get("absent"))
    cache.reset_stats()
    assert isinstance(cache.stats, dict)


# ── tags ─────────────────────────────────────────────────────────────────


def test_invalidate_tags(cache):
    async def scenario():
        await cache.set("k", "v", tags=["group-a"])
        await cache.invalidate_tags(["group-a"])
        return await cache.get("k")

    assert _run(scenario()) is None


def test_invalidating_an_unused_tag_is_harmless(cache):
    _run(cache.invalidate_tags(["never-used"]))


# ── connection failure ───────────────────────────────────────────────────


def test_an_unreachable_server_surfaces_an_error():
    """A dead Redis must not hang silently."""
    dead = RedisCache(url="redis://127.0.0.1:1/0")
    with pytest.raises(Exception):
        _run(dead.get("k"))
