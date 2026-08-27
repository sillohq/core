"""Coverage for sillo.work.queue.middleware's RateLimitMiddleware and
TimeoutMiddleware (the job-pipeline variants, distinct from
sillo.work.middleware's task-level ones), plus RetryMiddleware's
give-up-after-max-attempts path.
"""

from __future__ import annotations

import asyncio

import pytest

from sillo.work.queue.middleware import (
    RateLimitMiddleware,
    RetryMiddleware,
    TimeoutMiddleware,
)


async def test_rate_limit_middleware_allows_within_burst():
    middleware = RateLimitMiddleware(max_jobs=100, per_seconds=1, burst=2)

    calls = []

    async def handler():
        calls.append(1)
        return "ok"

    wrapped = middleware(handler)
    assert await asyncio.wait_for(wrapped(), timeout=1) == "ok"
    assert await asyncio.wait_for(wrapped(), timeout=1) == "ok"
    assert len(calls) == 2


async def test_rate_limit_middleware_waits_when_tokens_exhausted():
    middleware = RateLimitMiddleware(max_jobs=1000, per_seconds=1, burst=1)

    async def handler():
        return "ok"

    wrapped = middleware(handler)
    await wrapped()  # consumes the single burst token
    # Refill is fast (1000 jobs/sec), so the wait branch resolves quickly.
    assert await asyncio.wait_for(wrapped(), timeout=1) == "ok"


async def test_timeout_middleware_lets_fast_jobs_through():
    middleware = TimeoutMiddleware(seconds=1)

    async def handler():
        return "done"

    wrapped = middleware(handler)
    assert await wrapped() == "done"


async def test_timeout_middleware_raises_on_slow_jobs():
    middleware = TimeoutMiddleware(seconds=0.01)

    async def handler():
        await asyncio.sleep(1)

    wrapped = middleware(handler)
    with pytest.raises(asyncio.TimeoutError):
        await wrapped()


async def test_retry_middleware_gives_up_after_max_attempts():
    middleware = RetryMiddleware(max_attempts=2, base_delay=0.001)

    attempts = []

    async def handler():
        attempts.append(1)
        raise ValueError("always fails")

    wrapped = middleware(handler)
    with pytest.raises(ValueError, match="always fails"):
        await wrapped()
    assert len(attempts) == 2


async def test_retry_middleware_reraises_cancelled_error_immediately():
    middleware = RetryMiddleware(max_attempts=5, base_delay=0.001)

    async def handler():
        raise asyncio.CancelledError()

    wrapped = middleware(handler)
    with pytest.raises(asyncio.CancelledError):
        await wrapped()
