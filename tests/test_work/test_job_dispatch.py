"""
Dispatching jobs onto a queue.

Pushing is I/O, so ``dispatch`` is a coroutine. The blocking variants exist
for scripts and management commands, and refuse to run when a loop is already
going rather than raising ``This event loop is already running`` from inside
asyncio.
"""

import asyncio
import inspect
import json

import pytest

from sillo.work.queue.job import Job, dispatch


class RecordingConnection:
    """Stands in for a queue backend, recording what was pushed."""

    def __init__(self):
        self.pushed = []

    async def push(self, queue, payload, delay=0):
        self.pushed.append({"queue": queue, "payload": json.loads(payload), "delay": delay})
        return f"job-{len(self.pushed)}"


@pytest.fixture
def job_class():
    class SendWelcomeEmail(Job):
        queue = "emails"

        def __init__(self, user_id, greeting="hi"):
            self.user_id = user_id
            self.greeting = greeting

        async def handle(self):
            return f"{self.greeting} {self.user_id}"

    SendWelcomeEmail.on_connection(RecordingConnection())
    SendWelcomeEmail.on_queue("emails")
    return SendWelcomeEmail


# ── the async API ────────────────────────────────────────────────────────


async def test_dispatch_pushes_onto_the_queue(job_class):
    job_id = await job_class.dispatch("user-42")

    assert job_id == "job-1"
    assert job_class._connection.pushed == [
        {
            "queue": "emails",
            # Qualified, not bare: the worker is a separate process and has to
            # import the class before it can run it.
            "payload": {
                "job": job_class.job_reference(),
                "args": ["user-42"],
                "kwargs": {},
            },
            "delay": 0,
        }
    ]


async def test_keyword_arguments_survive_the_payload(job_class):
    await job_class.dispatch("user-42", greeting="hello")

    assert job_class._connection.pushed[0]["payload"]["kwargs"] == {"greeting": "hello"}


async def test_dispatch_after_carries_the_delay(job_class):
    await job_class.dispatch_after(300, "user-42")

    assert job_class._connection.pushed[0]["delay"] == 300


async def test_the_module_level_helper_dispatches_too(job_class):
    assert await dispatch(job_class, "user-42") == "job-1"
    assert len(job_class._connection.pushed) == 1


async def test_perform_now_runs_the_job_without_queueing(job_class):
    assert await job_class.perform_now("user-42") == "hi user-42"
    assert job_class._connection.pushed == []


async def test_a_missing_connection_names_the_setter(job_class):
    class Unwired(Job):
        async def handle(self):
            return None

    with pytest.raises(RuntimeError, match="on_connection"):
        await Unwired.dispatch()


# ── the blocking API ─────────────────────────────────────────────────────


def test_dispatch_blocking_works_from_synchronous_code(job_class):
    """The original defect: this raised no matter where it was called from."""
    assert job_class.dispatch_blocking("user-42") == "job-1"
    assert job_class._connection.pushed[0]["delay"] == 0


def test_dispatch_blocking_accepts_a_delay(job_class):
    job_class.dispatch_blocking("user-42", delay=60)

    assert job_class._connection.pushed[0]["delay"] == 60


def test_dispatch_sync_runs_the_job_inline(job_class):
    assert job_class.dispatch_sync("user-42") == "hi user-42"
    assert job_class._connection.pushed == []


async def test_dispatch_blocking_inside_a_loop_points_at_the_async_form(job_class):
    with pytest.raises(RuntimeError, match=r"await SendWelcomeEmail\.dispatch"):
        job_class.dispatch_blocking("user-42")


async def test_dispatch_sync_inside_a_loop_points_at_perform_now(job_class):
    with pytest.raises(RuntimeError, match=r"await SendWelcomeEmail\.perform_now"):
        job_class.dispatch_sync("user-42")


async def test_a_refused_blocking_call_does_not_leak_a_coroutine(job_class, recwarn):
    """The rejected coroutine is closed, so no 'never awaited' warning fires."""
    with pytest.raises(RuntimeError):
        job_class.dispatch_blocking("user-42")

    assert not [w for w in recwarn if "never awaited" in str(w.message)]


def test_dispatch_is_a_coroutine_function(job_class):
    assert inspect.iscoroutinefunction(job_class.dispatch)
    assert inspect.iscoroutinefunction(job_class.dispatch_after)
