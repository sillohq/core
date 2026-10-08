"""Contract tests for cache-backed lease locks."""

import asyncio

import pytest

from sillo.cache import LockNotAcquiredError, MemoryCache, RedisCache
from sillo.cache.base import BaseCache


class UnsupportedLockCache(MemoryCache):
    """Exercises BaseCache's explicit error for custom backends without locks."""

    _acquire_lock = BaseCache._acquire_lock
    _extend_lock = BaseCache._extend_lock
    _release_lock = BaseCache._release_lock


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": ""}, "non-empty"),
        ({"name": "job", "lease": 0}, "greater than zero"),
        ({"name": "job", "blocking_timeout": -1}, "non-negative"),
        ({"name": "job", "retry_interval": 0}, "greater than zero"),
    ],
)
def test_lock_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        MemoryCache().lock(**kwargs)


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
    assert await expired_owner.extend() is False
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


async def test_lock_stops_waiting_at_its_deadline():
    cache = MemoryCache()
    async with cache.lock("job"):
        contender = cache.lock("job", blocking_timeout=0.01, retry_interval=0.001)
        assert await contender.acquire() is False


async def test_context_raises_when_the_lock_is_unavailable():
    cache = MemoryCache()
    async with cache.lock("job"):
        with pytest.raises(LockNotAcquiredError):
            async with cache.lock("job"):
                pass


async def test_a_backend_without_lock_support_fails_explicitly():
    cache = UnsupportedLockCache()
    lock = cache.lock("job")
    with pytest.raises(NotImplementedError, match="does not support locks"):
        await lock.acquire()
    with pytest.raises(NotImplementedError, match="does not support locks"):
        await cache._extend_lock("job", "token", 1)
    with pytest.raises(NotImplementedError, match="does not support locks"):
        await cache._release_lock("job", "token")


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
