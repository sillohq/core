"""Coverage for RedisConnection._r()'s lazy-connect/cache behavior and the
blocking (timeout > 0) branch of pop(), against an in-process fakeredis
server rather than a real one — same approach as
test_redis_queue_reliability.py.
"""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)

from sillo.work.queue import connection as connection_module
from sillo.work.queue.connection import RedisConnection


@pytest.fixture(autouse=True)
def _fake_aioredis(monkeypatch):
    """Point RedisConnection._r()'s aioredis.from_url at a fake server."""
    server = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class FakeAioredisModule:
        @staticmethod
        def from_url(url, decode_responses=True):
            return server

    monkeypatch.setattr(connection_module, "aioredis", FakeAioredisModule)
    return server


async def test_r_connects_lazily_and_caches_the_client():
    conn = RedisConnection()
    assert conn._redis is None

    first = await conn._r()
    assert conn._redis is first

    second = await conn._r()
    assert second is first


async def test_pop_with_timeout_uses_blmove_and_claims_the_job():
    conn = RedisConnection(visibility_timeout=30.0)

    job_id = await conn.push("emails", "payload-a")
    result = await conn.pop("emails", timeout=1)

    assert result == (job_id, "payload-a")
    assert await conn.in_flight("emails") == 1


async def test_pop_with_timeout_returns_none_when_nothing_is_ready():
    conn = RedisConnection(visibility_timeout=30.0)
    assert await conn.pop("emails", timeout=0.1) is None
