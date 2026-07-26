from __future__ import annotations

import pytest

from sillo.security.ratelimit.backends import (
    InMemoryBackend,
    RateLimitBackend,
    get_backend,
)


@pytest.fixture
def backend():
    b = InMemoryBackend()
    return b


async def test_fetch_missing_returns_none(backend):
    assert await backend.fetch_state("missing") is None


async def test_save_and_fetch_roundtrip(backend):
    await backend.save_state("k", {"count": 1}, ttl=60)
    assert await backend.fetch_state("k") == {"count": 1}


async def test_expiry(backend):
    await backend.save_state("k", {"count": 1}, ttl=1)
    # simulate expiry by direct manipulation of internal store time
    import time

    backend._store["k"] = (backend._store["k"][0], time.time() - 1)
    assert await backend.fetch_state("k") is None


async def test_clear(backend):
    await backend.save_state("k", {"a": 1}, ttl=60)
    await backend.clear()
    assert await backend.fetch_state("k") is None


def test_get_backend_default_memory():
    assert isinstance(get_backend(None), InMemoryBackend)
    assert isinstance(get_backend("memory"), InMemoryBackend)


def test_get_backend_passthrough_instance():
    inst = InMemoryBackend()
    assert get_backend(inst) is inst


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError):
        get_backend("nope")


def test_inmemory_is_rate_limit_backend_subclass():
    assert isinstance(InMemoryBackend(), RateLimitBackend)
