"""Deep tests for sillo.work BackgroundTask lifecycle and Supervisor.
"""

import asyncio
import threading

import pytest

from sillo.work.background.supervisor import RestartPolicy, Supervisor
from sillo.work.background.tasks import BackgroundTask
from sillo.work.types import TaskError, TaskResult


async def test_run_success_and_wait():
    async def add(a, b):
        return a + b

    bt = BackgroundTask.run(add, 2, 3)
    assert bt.running or not bt.done  # started
    value = await bt.wait(timeout=2)
    assert value == 5
    assert bt.done


async def test_run_outside_async_context_raises():
    raised = []

    def sync_run():
        try:
            BackgroundTask.run(asyncio.sleep, 0)
        except RuntimeError:
            raised.append(True)

    # run where no event loop is active
    t = threading.Thread(target=sync_run)
    t.start()
    t.join()
    assert raised == [True]


async def test_on_success_callback_fires():
    seen = []

    async def job():
        return "ok"

    async def cb(r: TaskResult):
        seen.append(r.result)

    bt = BackgroundTask.run(job, on_success=cb)
    await bt.wait(timeout=2)
    await asyncio.sleep(0.02)
    assert seen == ["ok"]


async def test_on_failure_callback_fires():
    seen = []

    async def job():
        raise ValueError("x")

    async def cb(r: TaskResult):
        seen.append(r.error)

    bt = BackgroundTask.run(job, on_failure=cb)
    with pytest.raises(TaskError):
        await bt.wait(timeout=2)
    await asyncio.sleep(0.02)
    assert seen and "ValueError" in seen[0]


async def test_on_done_fires_for_failure():
    seen = []

    async def job():
        raise RuntimeError("boom")

    async def cb(r: TaskResult):
        seen.append(r.status.value)

    bt = BackgroundTask.run(job, on_done=cb)
    with pytest.raises(TaskError):
        await bt.wait(timeout=2)
    await asyncio.sleep(0.02)
    assert seen == ["failed"]


async def test_run_sync_wraps_sync_function():
    calls = []

    def sync_work(x):
        calls.append(x)
        return x * 2

    bt = BackgroundTask.run_sync(sync_work, 21)
    value = await bt.wait(timeout=2)
    assert value == 42
    assert calls == [21]


async def test_run_sync_completes():
    calls = []

    def sync_work(x):
        calls.append(x)
        return x * 2

    bt = BackgroundTask.run_sync(sync_work, 21)
    value = await bt.wait(timeout=2)
    assert value == 42
    assert calls == [21]


async def test_cancel_stops_task():
    BackgroundTask._instances.clear()
    async def slow():
        await asyncio.sleep(5)

    bt = BackgroundTask.run(slow)
    assert bt.cancel() is True
    # wait() must surface the cancellation (TaskCancelled)
    with pytest.raises(Exception):
        await bt.wait(timeout=2)
    await asyncio.sleep(0.02)
    # the task is no longer running after cancellation
    assert bt.running is False


async def test_drain_waits_for_all():
    BackgroundTask._instances.clear()

    async def short():
        await asyncio.sleep(0.05)
        return 1

    BackgroundTask.run(short)
    BackgroundTask.run(short)
    summary = await BackgroundTask.drain(timeout=3.0, cancel_remaining=False)
    assert summary["total"] == 2
    assert summary["completed"] == 2


async def test_count_reflects_tracked_tasks():
    BackgroundTask._instances.clear()

    async def short():
        await asyncio.sleep(0.05)

    BackgroundTask.run(short)
    c = BackgroundTask.count()
    assert c["total"] >= 1
    await BackgroundTask.drain(timeout=3.0, cancel_remaining=False)


async def test_cancel_after_completion_returns_false():
    async def quick():
        return 1

    bt = BackgroundTask.run(quick)
    await bt.wait(timeout=2)
    assert bt.cancel() is False


async def test_properties_before_and_after_completion():
    async def add(a, b):
        return a + b

    bt = BackgroundTask.run(add, 2, 3)

    assert isinstance(bt.id, str) and bt.id
    assert bt.name == "add"
    assert bt.elapsed >= 0
    assert bt.result is None  # not finished yet

    await bt.wait(timeout=2)

    assert bt.result is not None
    assert bt.result.result == 5


async def test_to_dict_before_and_after_completion():
    async def add(a, b):
        return a + b

    bt = BackgroundTask.run(add, 2, 3)
    pending = bt.to_dict()
    assert pending["result"] is None

    await bt.wait(timeout=2)
    finished = bt.to_dict()
    assert finished["done"] is True
    # TaskResult.to_dict() serialises `result` to its str() form.
    assert finished["result"]["result"] == "5"


async def test_run_sync_passes_through_an_already_async_function():
    async def already_async(x):
        return x * 3

    bt = BackgroundTask.run_sync(already_async, 7)
    assert await bt.wait(timeout=2) == 21


async def test_drain_with_no_tracked_tasks():
    BackgroundTask._instances.clear()
    summary = await BackgroundTask.drain()
    assert summary == {"total": 0, "completed": 0, "cancelled": 0}


async def test_drain_cancels_tasks_that_do_not_finish_in_time():
    BackgroundTask._instances.clear()

    async def slow():
        await asyncio.sleep(5)

    BackgroundTask.run(slow)
    summary = await BackgroundTask.drain(timeout=0.05, cancel_remaining=True)

    assert summary["total"] == 1
    assert summary["cancelled"] == 1
    assert summary["completed"] == 0


async def test_repr_includes_name_and_done_state():
    async def add(a, b):
        return a + b

    bt = BackgroundTask.run(add, 2, 3)
    assert repr(bt) == f"BackgroundTask(add, done={bt.done})"


async def test_supervisor_on_failure_restarts_until_exhausted():
    runs = []

    async def flaky():
        runs.append(1)
        raise RuntimeError("keep failing")

    sup = Supervisor(flaky, RestartPolicy.ON_FAILURE, max_restarts=2, base_delay=0.01)
    await sup.start()
    # initial + 2 restarts = 3 attempts
    assert len(runs) == 3
    assert sup.to_dict()["restarts"] == 2


async def test_supervisor_never_policy_stops_on_success():
    runs = []

    async def ok():
        runs.append(1)

    sup = Supervisor(ok, RestartPolicy.NEVER, max_restarts=5, base_delay=0.01)
    await sup.start()
    assert len(runs) == 1  # ran once, not restarted


async def test_supervisor_never_policy_does_not_restart_on_failure():
    runs = []

    async def flaky():
        runs.append(1)
        raise RuntimeError("nope")

    sup = Supervisor(flaky, RestartPolicy.NEVER, max_restarts=5, base_delay=0.01)
    await sup.start()
    assert len(runs) == 1  # failed once, never restarted


async def test_supervisor_always_policy_restarts_a_successful_task_too():
    runs = []

    async def ok():
        runs.append(1)

    sup = Supervisor(ok, RestartPolicy.ALWAYS, max_restarts=2, base_delay=0.01)
    await sup.start()
    # initial + 2 restarts, even though every run succeeded
    assert len(runs) == 3
    assert sup.to_dict()["restarts"] == 2


async def test_supervisor_start_stops_cleanly_when_its_own_task_is_cancelled():
    started = asyncio.Event()

    async def forever():
        started.set()
        await asyncio.sleep(30)

    sup = Supervisor(forever, RestartPolicy.NEVER)
    run_task = asyncio.ensure_future(sup.start())
    await started.wait()

    # Cancel the supervisor's own coroutine directly, rather than going
    # through stop() — this is what exercises start()'s own
    # `except asyncio.CancelledError: break`. start() catches it and
    # returns normally rather than propagating it.
    run_task.cancel()
    await run_task
    assert sup._stopped.is_set()


async def test_supervisor_stop_cancels_the_current_task():
    started = asyncio.Event()

    async def forever():
        started.set()
        await asyncio.sleep(30)

    sup = Supervisor(forever, RestartPolicy.NEVER)
    run_task = asyncio.ensure_future(sup.start())
    await started.wait()

    sup.stop()
    await sup.wait(timeout=2)

    assert sup._running is False
    await run_task
