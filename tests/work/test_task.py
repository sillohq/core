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
