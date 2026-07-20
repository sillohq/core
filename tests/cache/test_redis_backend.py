"""Tests for sillo.cache.backends.RedisCache.

These tests are skipped unless:
  * the optional ``redis`` package is importable, AND
  * a Redis server is reachable at REDIS_URL (default redis://localhost:6379/0).

Set REDIS_URL to run them; otherwise they are no-ops so the suite stays green
without a Redis instance.
"""

import os

import pytest

from sillo.cache.backends import RedisCache

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _have_redis() -> bool:
    try:
        import redis.asyncio  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _have_redis(), reason="redis package not installed (pip install sillo[cache])"
)


async def _backend():
    backend = RedisCache(url=REDIS_URL, namespace="sillo_test", default_ttl=60)
    # Probe connectivity; skip if no server.
    try:
        await backend.set("__probe__", 1)
        await backend.delete("__probe__")
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no Redis server at {REDIS_URL}: {exc}")
    await backend.clear()
    return backend


async def test_redis_set_get():
    c = await _backend()
    await c.set("k", {"v": 1})
    assert await c.get("k") == {"v": 1}
    await c.close()


async def test_redis_delete_exists():
    c = await _backend()
    await c.set("k", 1)
    assert await c.exists("k") is True
    assert await c.delete("k") is True
    assert await c.exists("k") is False
    await c.close()


async def test_redis_tags():
    c = await _backend()
    await c.set("a", 1, tags=["t1"])
    await c.set("b", 2, tags=["t2"])
    removed = await c.invalidate_tags("t1")
    assert removed >= 1
    assert await c.exists("a") is False
    await c.close()


async def test_redis_ttl():
    c = await _backend()
    await c.set("k", 1, ttl=1)
    assert await c.get("k") == 1
    import asyncio

    await asyncio.sleep(1.1)
    from sillo.cache.base import _MISSING

    assert await c.get("k") is _MISSING
    await c.close()
