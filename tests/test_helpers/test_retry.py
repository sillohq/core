"""Retry helpers: the decorator, and the sync and async one-shot forms."""

import asyncio

import pytest

from sillo.helpers.retry import (
    RetryError,
    _compute_delay,
    async_retry,
    retry,
    sync_retry,
)


def _run(coro):
    return asyncio.run(coro)


# ── backoff arithmetic ───────────────────────────────────────────────────


def test_delay_grows_with_each_attempt():
    first = _compute_delay(1, base=1.0, factor=2.0, cap=60.0, jitter=False)
    second = _compute_delay(2, base=1.0, factor=2.0, cap=60.0, jitter=False)
    assert second > first


def test_delay_is_capped():
    assert _compute_delay(20, base=1.0, factor=2.0, cap=5.0, jitter=False) <= 5.0


def test_jitter_stays_within_the_cap():
    for _ in range(20):
        assert _compute_delay(3, base=1.0, factor=2.0, cap=10.0, jitter=True) <= 10.0


def test_no_jitter_is_deterministic():
    a = _compute_delay(2, base=1.0, factor=2.0, cap=60.0, jitter=False)
    b = _compute_delay(2, base=1.0, factor=2.0, cap=60.0, jitter=False)
    assert a == b


# ── the decorator ────────────────────────────────────────────────────────


def test_a_succeeding_call_is_not_retried():
    calls = []

    @retry(max_attempts=3, base_delay=0)
    def works():
        calls.append(1)
        return "ok"

    assert works() == "ok"
    assert len(calls) == 1


def test_a_flaky_call_is_retried_until_it_succeeds():
    calls = []

    @retry(max_attempts=5, base_delay=0)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3


def test_exhausting_attempts_raises_retryerror_carrying_the_cause():
    """The original exception is wrapped, not re-raised, so callers can tell
    'gave up after N tries' apart from a first-attempt failure."""
    calls = []

    @retry(max_attempts=3, base_delay=0)
    def always_fails():
        calls.append(1)
        raise ConnectionError("down")

    with pytest.raises(RetryError) as info:
        always_fails()
    assert len(calls) == 3
    assert "3 attempts" in str(info.value)


def test_arguments_are_passed_through():
    @retry(max_attempts=2, base_delay=0)
    def add(a, b, c=0):
        return a + b + c

    assert add(1, 2, c=3) == 6


def test_the_decorator_works_on_async_functions():
    calls = []

    @retry(max_attempts=3, base_delay=0)
    async def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionError("not yet")
        return "ok"

    assert _run(flaky()) == "ok"


def test_a_single_attempt_means_no_retry():
    calls = []

    @retry(max_attempts=1, base_delay=0)
    def fails():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(RetryError):
        fails()
    assert len(calls) == 1


# ── sync_retry ───────────────────────────────────────────────────────────


def test_sync_retry_returns_the_value():
    assert sync_retry(lambda: "ok", max_attempts=3, base_delay=0) == "ok"


def test_sync_retry_retries():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return "ok"

    assert sync_retry(flaky, max_attempts=5, base_delay=0) == "ok"
    assert len(calls) == 3


def test_sync_retry_gives_up():
    def always_fails():
        raise ConnectionError("down")

    with pytest.raises(RetryError):
        sync_retry(always_fails, max_attempts=2, base_delay=0)


def test_sync_retry_forwards_arguments():
    assert sync_retry(lambda a, b: a + b, 1, 2, max_attempts=2, base_delay=0) == 3


# ── async_retry ──────────────────────────────────────────────────────────


def test_async_retry_returns_the_value():
    async def works():
        return "ok"

    assert _run(async_retry(works, max_attempts=3, base_delay=0)) == "ok"


def test_async_retry_retries():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return "ok"

    assert _run(async_retry(flaky, max_attempts=5, base_delay=0)) == "ok"
    assert len(calls) == 3


def test_async_retry_gives_up():
    async def always_fails():
        raise ConnectionError("down")

    with pytest.raises(RetryError):
        _run(async_retry(always_fails, max_attempts=2, base_delay=0))


def test_async_retry_forwards_arguments():
    async def add(a, b):
        return a + b

    assert _run(async_retry(add, 1, 2, max_attempts=2, base_delay=0)) == 3
