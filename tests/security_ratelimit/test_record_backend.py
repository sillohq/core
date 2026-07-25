from __future__ import annotations

import inspect

import pytest

from tortoise import Tortoise, run_async
from tortoise.exceptions import ConfigurationError

from sillo.security.ratelimit.backends import RecordBackend
from sillo.security.ratelimit.models import RateLimitCounter
from sillo.security.ratelimit.strategies import TokenBucketStrategy

_has_global_fallback = "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters


@pytest.fixture
async def record_backend():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.security.ratelimit.models"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas(safe=True)
    backend = RecordBackend()
    yield backend
    await backend.clear()
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass
    Tortoise._inited = False


async def test_record_backend_roundtrip(record_backend):
    await record_backend.save_state("k", {"tokens": 1.0, "last": 1000.0}, ttl=60)
    state = await record_backend.fetch_state("k")
    assert state == {"tokens": 1.0, "last": 1000.0}


async def test_record_backend_missing(record_backend):
    assert await record_backend.fetch_state("missing") is None


async def test_record_backend_expiry(record_backend):
    await record_backend.save_state("k", {"tokens": 1.0, "last": 1000.0}, ttl=1)
    # force expiry by updating the row's expires_at into the past
    row = await RateLimitCounter.get(key="k")
    row.expires_at = 1
    await row.save()
    assert await record_backend.fetch_state("k") is None


async def test_record_backend_strategy_integration(record_backend):
    s = TokenBucketStrategy()
    limit, window = 2, 10
    for _ in range(2):
        r = await s.hit(record_backend, "k", limit, window, now=1000.0)
        assert r.allowed
    denied = await s.hit(record_backend, "k", limit, window, now=1000.0)
    assert not denied.allowed


async def test_record_backend_clear(record_backend):
    await record_backend.save_state("k", {"tokens": 1.0, "last": 1.0}, ttl=60)
    await record_backend.clear()
    assert await record_backend.fetch_state("k") is None
