"""Contract tests for cache-backed lease locks."""

import asyncio

import pytest

from sillo.cache import LockNotAcquiredError, MemoryCache, RedisCache


async def test_memory_lock_has_one_owner_and_releases():
    cache = MemoryCache()
    first = cache.lock("scheduler", lease=1)
    second = cache.lock("scheduler", lease=1)

    assert await first.acquire() is True
    assert await second.acquire() is False
    assert await first.release() is True
    assert await second.acquire() is True


async def test_lock_context_releases_after_an_exception():
    cache = MemoryCache()
    with pytest.raises(ValueError):
        async with cache.lock("job"):
            raise ValueError("boom")
    assert await cache.lock("job").acquire() is True


async def test_only_the_owner_can_extend_or_release():
    cache = MemoryCache()
    owner = cache.lock("job", lease=1)
    other = cache.lock("job", lease=1)
    assert await owner.acquire()
    assert await other.release() is False
    assert await other.extend() is False
    assert await owner.extend(lease=2) is True


async def test_an_expired_owner_cannot_release_a_new_owner_lock():
    cache = MemoryCache()
    expired_owner = cache.lock("job", lease=0.01)
    assert await expired_owner.acquire()
    await asyncio.sleep(0.02)
    new_owner = cache.lock("job")
    assert await new_owner.acquire()
    assert await expired_owner.release() is False
    assert new_owner.acquired is True


async def test_lock_can_wait_for_a_release():
    cache = MemoryCache()
    first = cache.lock("job")
    assert await first.acquire()
    waiting = cache.lock("job", blocking_timeout=0.2, retry_interval=0.01)
    task = asyncio.create_task(waiting.acquire())
    await asyncio.sleep(0.03)
    await first.release()
    assert await task is True


async def test_context_raises_when_the_lock_is_unavailable():
    cache = MemoryCache()
    async with cache.lock("job"):
        with pytest.raises(LockNotAcquiredError):
            async with cache.lock("job"):
                pass


try:
    import fakeredis.aioredis
except ImportError:  # pragma: no cover - depends on the optional test extra
    fakeredis = None
else:
    import fakeredis


@pytest.mark.skipif(fakeredis is None, reason="fakeredis provides Redis lock coverage")
async def test_redis_lock_is_owner_safe_and_renewable():
    cache = RedisCache(client=fakeredis.aioredis.FakeRedis(decode_responses=False))
    owner = cache.lock("scheduler", lease=10)
    contender = cache.lock("scheduler", lease=10)

    assert await owner.acquire() is True
    assert await contender.acquire() is False
    assert await contender.release() is False
    assert await owner.extend() is True
    assert await owner.release() is True
    assert await contender.acquire() is True
