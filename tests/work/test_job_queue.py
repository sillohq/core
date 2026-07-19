"""Deep tests for sillo.work job queue: SyncConnection, ConnectionManager,
PayloadSerializer, and Job.fire() through middleware pipelines.
"""

import asyncio

import pytest

from sillo.work.queue.connection import ConnectionManager, SyncConnection
from sillo.work.queue.job import Job
from sillo.work.queue.middleware import (
    RetryMiddleware,
    TimeoutMiddleware,
)
from sillo.work.queue.payloads import PayloadSerializer


def test_payload_serializer_roundtrip():
    ser = PayloadSerializer()
    raw = ser.serialize(
        "tests.work.work_jobs.SendEmail",
        {"to": "a@b.com", "subject": "Hi"},
        max_tries=2,
        timeout=15,
        queue="emails",
    )
    decoded = ser.deserialize(raw)
    assert decoded["job_class"] == "tests.work.work_jobs.SendEmail"
    assert decoded["data"] == {"to": "a@b.com", "subject": "Hi"}
    assert decoded["max_tries"] == 2
    assert decoded["queue"] == "emails"


async def test_sync_connection_push_pop_roundtrip():
    conn = SyncConnection()
    payload = '{"job": "X", "data": {}}'
    job_id = await conn.push("default", payload)
    popped = await conn.pop("default")
    assert popped is not None
    assert popped[0] == job_id
    assert popped[1] == payload


async def test_sync_connection_size_and_clear():
    conn = SyncConnection()
    await conn.push("q1", "p1")
    await conn.push("q1", "p2")
    assert await conn.size("q1") == 2
    await conn.clear("q1")
    assert await conn.size("q1") == 0
    assert await conn.pop("q1", timeout=0.01) is None


async def test_sync_connection_empty_pop_returns_none():
    conn = SyncConnection()
    assert await conn.pop("default", timeout=0.01) is None


async def test_connection_manager_routes_by_name():
    mgr = ConnectionManager()
    mgr.add("default", SyncConnection()).add("emails", SyncConnection())
    await mgr.connection("emails").push("emails", "job-payload")
    assert await mgr.connection("emails").size("emails") == 1
    assert await mgr.connection("default").size("default") == 0
    # unknown connection raises
    with pytest.raises(KeyError):
        mgr.connection("missing")


class FlakyJob(Job):
    """Fails once, then succeeds. Middleware is a class var because
    Job.middleware_pipeline() reads self.__class__.middleware."""

    middleware = [RetryMiddleware(max_attempts=3, base_delay=0.01)]
    attempts: list = []

    def __init__(self):
        self.attempts = []

    async def handle(self):
        self.attempts.append(1)
        if len(self.attempts) < 2:
            raise RuntimeError("transient")
        return "ok"


class AlwaysFailsJob(Job):
    middleware = [RetryMiddleware(max_attempts=2, base_delay=0.01)]

    def __init__(self):
        self.n = 0

    async def handle(self):
        self.n += 1
        raise ValueError("nope")


class SlowJob(Job):
    # timeout=None so fire() does not wrap handle() in its own wait_for,
    # letting the TimeoutMiddleware enforce the deadline.
    timeout = None
    middleware = [TimeoutMiddleware(seconds=0.1)]

    async def handle(self):
        await asyncio.sleep(2)
        return "done"


async def test_job_fire_runs_handle_directly():
    from tests.work.work_jobs import SendEmail

    job = SendEmail(to="x@y.com")
    result = await job.fire()
    assert result == "sent:x@y.com"


async def test_retry_middleware_retries_until_success():
    job = FlakyJob()
    result = await job.fire()
    assert result == "ok"
    assert len(job.attempts) == 2


async def test_retry_middleware_gives_up_after_max_attempts():
    job = AlwaysFailsJob()
    with pytest.raises(ValueError):
        await job.fire()
    assert job.n == 2


async def test_timeout_middleware_cancels_slow_job():
    job = SlowJob()
    with pytest.raises(asyncio.TimeoutError):
        await job.fire()


async def test_fire_without_middleware_runs_handle():
    class Plain(Job):
        async def handle(self):
            return 42

    job = Plain()
    assert await job.fire() == 42
