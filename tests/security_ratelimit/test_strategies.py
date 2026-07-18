from __future__ import annotations

import pytest

from sillo.security.ratelimit.backends import InMemoryBackend
from sillo.security.ratelimit.strategies import (
    FixedWindowStrategy,
    SlidingWindowStrategy,
    TokenBucketStrategy,
    get_strategy,
)


@pytest.fixture
def memory():
    return InMemoryBackend()


# ---------------------------------------------------------------------------
# Token bucket
# ---------------------------------------------------------------------------


async def test_token_bucket_allows_up_to_limit(memory):
    s = TokenBucketStrategy()
    limit, window = 3, 10
    for _ in range(3):
        r = await s.hit(memory, "k", limit, window, now=1000.0)
        assert r.allowed
    denied = await s.hit(memory, "k", limit, window, now=1000.0)
    assert not denied.allowed
    assert denied.remaining == 0


async def test_token_bucket_refills_over_time(memory):
    s = TokenBucketStrategy()
    limit, window = 2, 10  # refill rate = 0.2 tokens/sec
    for _ in range(2):
        await s.hit(memory, "k", limit, window, now=1000.0)
    denied = await s.hit(memory, "k", limit, window, now=1000.0)
    assert not denied.allowed
    # 1 token refills after 5s -> at 1005.0 one request allowed
    ok = await s.hit(memory, "k", limit, window, now=1005.0)
    assert ok.allowed
    assert ok.remaining == 0


async def test_token_bucket_retry_after_positive(memory):
    s = TokenBucketStrategy()
    limit, window = 1, 10
    await s.hit(memory, "k", limit, window, now=1000.0)
    denied = await s.hit(memory, "k", limit, window, now=1000.0)
    assert denied.retry_after >= 1


# ---------------------------------------------------------------------------
# Fixed window
# ---------------------------------------------------------------------------


async def test_fixed_window_resets_each_window(memory):
    s = FixedWindowStrategy()
    limit, window = 2, 10
    for _ in range(2):
        assert (await s.hit(memory, "k", limit, window, now=1000.0)).allowed
    assert not (await s.hit(memory, "k", limit, window, now=1000.0)).allowed
    # Next window starts at 1010
    assert (await s.hit(memory, "k", limit, window, now=1010.0)).allowed


async def test_fixed_window_boundary_reset(memory):
    s = FixedWindowStrategy()
    limit, window = 1, 10
    assert (await s.hit(memory, "k", limit, window, now=1000.0)).allowed
    assert not (await s.hit(memory, "k", limit, window, now=1009.0)).allowed
    # exactly at next window start
    assert (await s.hit(memory, "k", limit, window, now=1010.0)).allowed


async def test_fixed_window_remaining_counts_down(memory):
    s = FixedWindowStrategy()
    limit, window = 3, 10
    r1 = await s.hit(memory, "k", limit, window, now=0.0)
    assert r1.remaining == 2
    r2 = await s.hit(memory, "k", limit, window, now=0.0)
    assert r2.remaining == 1


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------


async def test_sliding_window_blocks_trailing_window(memory):
    s = SlidingWindowStrategy()
    limit, window = 2, 10
    assert (await s.hit(memory, "k", limit, window, now=1000.0)).allowed
    assert (await s.hit(memory, "k", limit, window, now=1001.0)).allowed
    # 3rd within trailing 10s window is denied
    denied = await s.hit(memory, "k", limit, window, now=1005.0)
    assert not denied.allowed
    # old hit at 1000 expires after 1010 -> allowed again
    assert (await s.hit(memory, "k", limit, window, now=1011.0)).allowed


async def test_sliding_window_retry_after_uses_oldest(memory):
    s = SlidingWindowStrategy()
    limit, window = 1, 10
    await s.hit(memory, "k", limit, window, now=1000.0)
    denied = await s.hit(memory, "k", limit, window, now=1001.0)
    # oldest at 1000, frees at 1010 -> retry ~9s
    assert denied.retry_after <= 10


# ---------------------------------------------------------------------------
# Cost / weight
# ---------------------------------------------------------------------------


async def test_cost_consumes_multiple_tokens(memory):
    s = TokenBucketStrategy()
    limit, window = 2, 10
    r = await s.hit(memory, "k", limit, window, cost=2, now=1000.0)
    assert r.allowed
    assert r.remaining == 0
    denied = await s.hit(memory, "k", limit, window, cost=1, now=1000.0)
    assert not denied.allowed


# ---------------------------------------------------------------------------
# Strategy factory
# ---------------------------------------------------------------------------


def test_get_strategy_default_is_token():
    assert isinstance(get_strategy(None), TokenBucketStrategy)


def test_get_strategy_names():
    assert isinstance(get_strategy("fixed"), FixedWindowStrategy)
    assert isinstance(get_strategy("sliding"), SlidingWindowStrategy)
    assert isinstance(get_strategy("token"), TokenBucketStrategy)


def test_get_strategy_passthrough_instance():
    inst = FixedWindowStrategy()
    assert get_strategy(inst) is inst


def test_get_strategy_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        get_strategy("bogus")
