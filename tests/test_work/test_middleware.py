"""Coverage for sillo.work.middleware's three built-in middlewares, which had
no direct tests: TimeoutMiddleware, RateLimitMiddleware, and LoggingMiddleware.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from sillo.work.middleware import (
    LoggingMiddleware,
    RateLimitMiddleware,
    TimeoutMiddleware,
)
from sillo.work.task import Task
from sillo.work.types import TaskResult, TaskStatus


async def _noop():
    return None


def _make_task(**kwargs):
    return Task(_noop, name="job", **kwargs)


def _make_result(**kwargs):
    defaults = dict(task_id="t1", name="job", status=TaskStatus.COMPLETED)
    defaults.update(kwargs)
    return TaskResult(**defaults)


async def test_timeout_middleware_sets_timeout_when_absent():
    middleware = TimeoutMiddleware(timeout=5.0)
    task = _make_task()
    assert task.timeout is None

    await middleware.before_execute(task)

    assert task.timeout == 5.0


async def test_timeout_middleware_does_not_override_existing_timeout():
    middleware = TimeoutMiddleware(timeout=5.0)
    task = _make_task(timeout=1.0)

    await middleware.before_execute(task)

    assert task.timeout == 1.0


async def test_timeout_middleware_other_hooks_are_noops():
    middleware = TimeoutMiddleware(timeout=5.0)
    task = _make_task()
    result = _make_result()

    await middleware.before_enqueue(task)
    await middleware.after_execute(result)
    await middleware.on_error(task, ValueError("boom"))


async def test_rate_limit_middleware_allows_within_burst():
    middleware = RateLimitMiddleware(max_per_second=100, burst=2)
    task = _make_task()

    # Should not block for either of the two burst slots.
    await asyncio.wait_for(middleware.before_execute(task), timeout=1)
    await asyncio.wait_for(middleware.before_execute(task), timeout=1)


async def test_rate_limit_middleware_waits_when_tokens_exhausted():
    middleware = RateLimitMiddleware(max_per_second=1000, burst=1)
    task = _make_task()

    await middleware.before_execute(task)  # consumes the single token
    # The next call has to wait for a refill; with max_per_second=1000 that's
    # ~1ms, so this stays well under the timeout while still exercising the
    # wait branch.
    await asyncio.wait_for(middleware.before_execute(task), timeout=1)


async def test_rate_limit_middleware_other_hooks_are_noops():
    middleware = RateLimitMiddleware(max_per_second=10)
    task = _make_task()
    result = _make_result()

    await middleware.before_enqueue(task)
    await middleware.after_execute(result)
    await middleware.on_error(task, ValueError("boom"))


async def test_logging_middleware_logs_each_hook(caplog):
    middleware = LoggingMiddleware(level=logging.INFO)
    task = _make_task()
    result = _make_result(started_at=1.0, completed_at=1.5)

    with caplog.at_level(logging.INFO, logger="sillo.work.middleware"):
        await middleware.before_enqueue(task)
        await middleware.before_execute(task)
        await middleware.after_execute(result)
        await middleware.on_error(task, ValueError("boom"))

    messages = "\n".join(caplog.messages)
    assert "ENQUEUE job" in messages
    assert "START   job" in messages
    assert "DONE    job" in messages and "ok=True" in messages
    assert "ERROR   job" in messages and "ValueError" in messages
