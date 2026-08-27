"""Deep tests for sillo.work Task lifecycle, hooks, timeout, and decorator."""

import asyncio

import pytest

from sillo.work.task import Task, task
from sillo.work.types import (
    TaskCancelled,
    TaskError,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskTimeout,
)


async def _add(a, b):
    return a + b


async def _boom():
    raise ValueError("kaboom")


async def test_run_success_returns_value_and_marks_completed():
    t = Task(_add, 2, 3, name="add")
    value = await t.run()
    assert value == 5
    assert t.status == TaskStatus.COMPLETED
    assert t.result is not None
    assert t.result.result == 5
    assert t.result.ok is True


async def test_run_failure_reraises_and_marks_failed():
    t = Task(_boom, name="boom", max_attempts=1)
    with pytest.raises(ValueError):
        await t.run()
    assert t.status == TaskStatus.FAILED
    assert t.result is not None
    assert t.result.status == TaskStatus.FAILED
    assert t.result.ok is False
    assert "ValueError" in (t.result.error or "")


async def test_run_with_max_attempts_uses_retrying_state():
    t = Task(_boom, name="retry", max_attempts=3)
    with pytest.raises(ValueError):
        await t.run()
    assert t.attempt == 1
    assert t.status == TaskStatus.RETRYING


async def test_cannot_run_task_twice():
    t = Task(_add, 1, 1, name="once")
    await t.run()
    with pytest.raises(TaskError):
        await t.run()


async def test_before_and_after_hooks_fire():
    events = []

    async def before(tk):
        events.append(("before", tk.name))

    async def after(tk):
        events.append(("after", tk.name))

    t = Task(_add, 1, 2, name="hk")
    t.before(before).after(after)
    await t.run()
    assert ("before", "hk") in events
    assert ("after", "hk") in events
    # before must run before after
    assert events.index(("before", "hk")) < events.index(("after", "hk"))


async def test_after_hook_fires_even_on_failure():
    events = []

    async def after(tk):
        events.append("after")

    t = Task(_boom, name="hkf", max_attempts=1)
    t.after(after)
    with pytest.raises(ValueError):
        await t.run()
    assert "after" in events


async def test_on_success_callback_receives_result():
    seen = []
    t = Task(_add, 4, 5, name="ok")
    t.on_success(lambda r: seen.append(r.result))
    await t.run()
    # success callback scheduled via create_task; yield to let it run
    await asyncio.sleep(0.01)
    assert seen == [9]


async def test_on_failure_callback_receives_result():
    seen = []
    t = Task(_boom, name="fail", max_attempts=1)
    t.on_failure(lambda r: seen.append(r.status))
    with pytest.raises(ValueError):
        await t.run()
    await asyncio.sleep(0.01)
    assert seen == [TaskStatus.FAILED]


async def test_timeout_marks_task_timeout():
    async def slow():
        await asyncio.sleep(2)
        return "done"

    t = Task(slow, name="slow")
    with pytest.raises(TaskTimeout):
        await t.run(timeout=0.1)
    assert t.status == TaskStatus.FAILED
    assert isinstance(t.result.error, str)
    assert "timed out" in t.result.error


async def test_wait_returns_value_after_completion():
    t = Task(_add, 10, 20, name="w")
    asyncio.create_task(t.run())
    value = await t.wait()
    assert value == 30


async def test_wait_raises_on_failure():
    t = Task(_boom, name="wf", max_attempts=1)
    asyncio.create_task(t.run())
    with pytest.raises(TaskError):
        await t.wait()


async def test_to_dict_reflects_state():
    t = Task(_add, 1, 2, name="d", priority=TaskPriority.HIGH)
    await t.run()
    d = t.to_dict()
    assert d["name"] == "d"
    assert d["priority"] == "HIGH"
    assert d["status"] == "completed"
    assert d["attempt"] == 1


async def test_lt_orders_by_priority_then_created():
    t1 = Task(_add, 1, 1, name="n1", priority=TaskPriority.LOW)
    await asyncio.sleep(0.001)
    t2 = Task(_add, 1, 1, name="n2", priority=TaskPriority.HIGH)
    assert (t2 < t1) is True
    assert (t1 < t2) is False


async def test_serialize_contains_expected_keys():
    t = Task(_add, 1, 2, name="s", priority=TaskPriority.CRITICAL, queue_name="q")
    payload = t.serialize()
    assert "id" in payload
    assert "name" in payload
    assert "priority" in payload
    assert "queue_name" in payload


def test_task_decorator_tags_function():
    @task(name="echo", priority=TaskPriority.HIGH, max_attempts=3, queue="emails")
    async def echo(msg):
        return msg

    assert getattr(echo, "_work_task") is True
    assert echo._work_name == "echo"
    assert echo._work_priority == TaskPriority.HIGH
    assert echo._work_max_attempts == 3
    assert echo._work_queue == "emails"


async def test_is_running_reflects_status():
    t = Task(_add, 1, 2, name="r")
    assert t.is_running is False
    await t.run()
    assert t.is_running is False  # completed, not running anymore


def test_then_chains_next_task_metadata():
    first = Task(_add, 1, 2, name="first")
    second = Task(_add, 3, 4, name="second")

    result = first.then(second)

    assert result is first
    assert "_chain" in first.metadata
    assert first._hooks["success"]


def test_catch_registers_fallback_metadata():
    main = Task(_boom, name="main")
    fallback = Task(_add, 1, 2, name="fallback")

    result = main.catch(fallback)

    assert result is main
    assert "_fallback" in main.metadata
    assert main._hooks["failure"]


async def test_hook_exceptions_are_logged_not_raised():
    async def bad_hook(t):
        raise RuntimeError("hook exploded")

    t = Task(_add, 1, 2, name="hooked")
    t.before(bad_hook)
    # Should not raise despite the before-hook failing.
    assert await t.run() == 3


async def test_wait_returns_immediately_when_result_already_set():
    t = Task(_add, 1, 2, name="already-done")
    await t.run()
    # result is already populated, so wait() takes the fast path.
    assert await t.wait() == 3


async def test_unwrap_result_returns_none_when_no_result():
    t = Task(_add, 1, 2, name="empty")
    assert t._unwrap_result() is None


async def test_complete_cancelled_sets_status_and_raises():
    t = Task(_add, 1, 2, name="cancel-me")
    t.status = TaskStatus.RUNNING
    with pytest.raises(asyncio.CancelledError):
        t._complete_cancelled()
    assert t.status == TaskStatus.CANCELLED
    assert t.result.status == TaskStatus.CANCELLED


async def test_unwrap_result_raises_task_cancelled():
    t = Task(_add, 1, 2, name="cancel-me")
    t.status = TaskStatus.RUNNING
    with pytest.raises(asyncio.CancelledError):
        t._complete_cancelled()

    with pytest.raises(TaskCancelled):
        t._unwrap_result()


def test_cancel_returns_false_without_an_underlying_asyncio_task():
    t = Task(_add, 1, 2, name="uncancellable")
    assert t.cancel() is False


async def test_run_handles_cancelled_error_from_the_wrapped_function():
    async def _cancels():
        raise asyncio.CancelledError()

    t = Task(_cancels, name="cancel-in-run")
    with pytest.raises(asyncio.CancelledError):
        await t.run()
    assert t.status == TaskStatus.CANCELLED


def test_repr_contains_name_status_and_attempt():
    t = Task(_add, 1, 2, name="reprable")
    text = repr(t)
    assert "reprable" in text
    assert t.status.value in text


def test_cancel_delegates_to_underlying_asyncio_task():
    class FakeAsyncioTask:
        def __init__(self):
            self.cancelled = False

        def done(self):
            return False

        def cancel(self):
            self.cancelled = True
            return True

    t = Task(_add, 1, 2, name="cancellable")
    fake = FakeAsyncioTask()
    t._task = fake
    assert t.cancel() is True
    assert fake.cancelled is True
