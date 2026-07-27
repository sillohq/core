"""
Per-job scheduler middleware: timeout, rate limit, and retry.

Each factory takes ``(handler, job)`` and returns a new zero-argument handler,
so the tests wrap a recording coroutine and assert on how many times — and
how fast — it was allowed to run. Sleeps are patched out where the assertion
is about the decision rather than the wall clock.
"""

import asyncio
import time

import pytest

from sillo.work.scheduler.middleware import (
    rate_limit_middleware,
    retry_middleware,
    timeout_middleware,
)


def _run(coro):
    return asyncio.run(coro)


class Job:
    """The middleware only reads ``job.name``, for its log line."""

    def __init__(self, name="nightly-report"):
        self.name = name


@pytest.fixture
def job():
    return Job()


def _counter(result="ok"):
    calls = []

    async def handler():
        calls.append(time.monotonic())
        return result

    return handler, calls


# ── timeout ──────────────────────────────────────────────────────────────


def test_a_fast_job_returns_its_value(job):
    async def scenario():
        handler, _ = _counter("done")
        wrapped = await timeout_middleware(handler, job, seconds=1)
        return await wrapped()

    assert _run(scenario()) == "done"


def test_a_job_that_overruns_is_cancelled(job):
    async def scenario():
        async def slow():
            await asyncio.sleep(5)

        wrapped = await timeout_middleware(slow, job, seconds=0.01)
        await wrapped()

    with pytest.raises(asyncio.TimeoutError):
        _run(scenario())


def test_the_deadline_does_not_fire_early(job):
    async def scenario():
        async def brief():
            await asyncio.sleep(0.01)
            return "finished"

        wrapped = await timeout_middleware(brief, job, seconds=2)
        return await wrapped()

    assert _run(scenario()) == "finished"


def test_the_wrapper_can_be_reused(job):
    async def scenario():
        handler, calls = _counter()
        wrapped = await timeout_middleware(handler, job, seconds=1)
        await wrapped()
        await wrapped()
        return len(calls)

    assert _run(scenario()) == 2


def test_an_exception_from_the_job_propagates(job):
    async def scenario():
        async def failing():
            raise ValueError("job failed")

        wrapped = await timeout_middleware(failing, job, seconds=1)
        await wrapped()

    with pytest.raises(ValueError, match="job failed"):
        _run(scenario())


def test_the_default_deadline_is_generous(job):
    async def scenario():
        handler, _ = _counter()
        wrapped = await timeout_middleware(handler, job)
        return await wrapped()

    assert _run(scenario()) == "ok"


# ── rate limit ───────────────────────────────────────────────────────────


def test_a_run_within_budget_is_immediate(job):
    async def scenario():
        handler, _ = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=10)
        started = time.monotonic()
        await wrapped()
        return time.monotonic() - started

    assert _run(scenario()) < 0.2


def test_the_job_result_passes_through(job):
    async def scenario():
        handler, _ = _counter("payload")
        wrapped = await rate_limit_middleware(handler, job, max_per_second=10)
        return await wrapped()

    assert _run(scenario()) == "payload"


def test_the_full_bucket_allows_a_burst(job):
    """The bucket starts full, so ``max_per_second`` runs go through without
    any waiting."""

    async def scenario():
        handler, calls = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=5)
        started = time.monotonic()
        for _ in range(5):
            await wrapped()
        return len(calls), time.monotonic() - started

    count, elapsed = _run(scenario())
    assert count == 5
    assert elapsed < 0.2


def test_exceeding_the_budget_waits(job, monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def scenario():
        handler, calls = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=2)
        for _ in range(4):
            await wrapped()
        return len(calls)

    assert _run(scenario()) == 4
    assert slept, "the fourth call should have had to wait for a token"


def test_the_wait_is_proportional_to_the_rate(job, monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def scenario(rate):
        slept.clear()
        handler, _ = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=rate)
        for _ in range(int(rate) + 2):
            await wrapped()
        return list(slept)

    slow = _run(scenario(1))
    fast = _run(scenario(10))
    assert max(slow) > max(fast)


def test_every_call_still_runs_the_job(job, monkeypatch):
    """Rate limiting delays work; it never silently drops it."""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def scenario():
        handler, calls = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=1)
        for _ in range(5):
            await wrapped()
        return len(calls)

    assert _run(scenario()) == 5


def test_tokens_refill_over_time(job):
    async def scenario():
        handler, calls = _counter()
        wrapped = await rate_limit_middleware(handler, job, max_per_second=100)
        await wrapped()
        await asyncio.sleep(0.05)
        await wrapped()
        return len(calls)

    assert _run(scenario()) == 2


# ── retry ────────────────────────────────────────────────────────────────


def test_a_succeeding_job_runs_once(job):
    async def scenario():
        handler, calls = _counter()
        wrapped = await retry_middleware(handler, job, max_attempts=3, base_delay=0)
        result = await wrapped()
        return result, len(calls)

    assert _run(scenario()) == ("ok", 1)


def test_a_flaky_job_is_retried_until_it_succeeds(job, monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    async def scenario():
        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("not yet")
            return "recovered"

        wrapped = await retry_middleware(flaky, job, max_attempts=5, base_delay=0)
        return await wrapped()

    assert _run(scenario()) == "recovered"
    assert len(calls) == 3


def test_the_last_failure_is_raised_after_the_final_attempt(job, monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    async def scenario():
        async def always_fails():
            calls.append(1)
            raise ConnectionError("down")

        wrapped = await retry_middleware(always_fails, job, max_attempts=3, base_delay=0)
        return await wrapped()

    with pytest.raises(ConnectionError, match="down"):
        _run(scenario())
    assert len(calls) == 3


def test_the_backoff_doubles_between_attempts(job, monkeypatch):
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def scenario():
        async def always_fails():
            raise ConnectionError("down")

        wrapped = await retry_middleware(always_fails, job, max_attempts=4, base_delay=1)
        return await wrapped()

    with pytest.raises(ConnectionError):
        _run(scenario())
    assert delays == [1, 2, 4]


def test_a_single_attempt_means_no_retry(job):
    calls = []

    async def scenario():
        async def failing():
            calls.append(1)
            raise ValueError("nope")

        wrapped = await retry_middleware(failing, job, max_attempts=1, base_delay=0)
        return await wrapped()

    with pytest.raises(ValueError):
        _run(scenario())
    assert len(calls) == 1


def test_cancellation_is_not_retried(job):
    """A cancelled job is being shut down deliberately; retrying would fight
    the scheduler's own stop signal."""
    calls = []

    async def scenario():
        async def cancelled():
            calls.append(1)
            raise asyncio.CancelledError()

        wrapped = await retry_middleware(cancelled, job, max_attempts=5, base_delay=0)
        return await wrapped()

    with pytest.raises(asyncio.CancelledError):
        _run(scenario())
    assert len(calls) == 1


def test_the_retry_log_names_the_job(job, monkeypatch, caplog):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def scenario():
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise ConnectionError("not yet")
            return "ok"

        wrapped = await retry_middleware(flaky, job, max_attempts=3, base_delay=0)
        return await wrapped()

    with caplog.at_level("WARNING"):
        assert _run(scenario()) == "ok"
    assert "nightly-report" in caplog.text


# ── composition ──────────────────────────────────────────────────────────


def test_retry_and_timeout_compose(job, monkeypatch):
    """Retry outside timeout gives 'retry a job that hangs', which is the
    combination worth having."""
    calls = []

    async def scenario():
        async def sometimes_hangs():
            calls.append(1)
            if len(calls) == 1:
                await asyncio.sleep(5)
            return "eventually"

        inner = await timeout_middleware(sometimes_hangs, job, seconds=0.01)
        outer = await retry_middleware(inner, job, max_attempts=3, base_delay=0)
        return await outer()

    assert _run(scenario()) == "eventually"
    assert len(calls) == 2


def test_rate_limit_and_retry_compose(job, monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    async def scenario():
        async def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise ConnectionError("not yet")
            return "done"

        inner = await rate_limit_middleware(flaky, job, max_per_second=100)
        outer = await retry_middleware(inner, job, max_attempts=3, base_delay=0)
        return await outer()

    assert _run(scenario()) == "done"
