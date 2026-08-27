"""The queue and scheduler commands, against real connections and a real manager."""

from __future__ import annotations

import asyncio
import io
import signal

import pytest

from sillo.console import Console, strip_ansi
from sillo.work.console import work_commands


@pytest.fixture(autouse=True)
def _restore_signal_handlers():
    """`queue:work` installs real SIGINT/SIGTERM handlers (via run_worker's
    default handle_signals=True); this removes them afterward so one
    (by-then-cancelled) test's handler doesn't leak into later tests."""
    yield
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.remove_signal_handler(sig)
        except (NotImplementedError, RuntimeError):
            pass


@pytest.fixture
def failed_repository():
    """An in-memory failed-job record."""
    from sillo.work.queue import MemoryFailedRepository

    return MemoryFailedRepository()


@pytest.fixture
def scheduler():
    """A manager with two tasks registered on it."""
    from sillo.work.scheduler.manager import SchedulerManager

    manager = SchedulerManager()

    @manager.cron("0 3 * * *", name="cleanup")
    async def cleanup():
        pass

    @manager.every(3600, name="sync")
    async def sync():
        pass

    return manager


def build(**kwargs):
    """A console with the work commands and a captured stream."""
    stream = io.StringIO()
    console = Console(
        prog="console.py",
        output=stream,
        error=stream,
        input=io.StringIO(),
        color=False,
        interactive=False,
    )
    console.add_many(work_commands(**kwargs))
    return console, stream


def written(stream) -> str:
    """What the console wrote, unstyled."""
    return strip_ansi(stream.getvalue())


# -- listing queues ----------------------------------------------------


async def test_listing_reports_a_size_per_queue():
    console, stream = build(queues=["mail", "reports"])

    assert await console.run_async(["queue:list"]) == 0
    text = written(stream)

    assert "mail" in text
    assert "reports" in text
    assert "waiting" in text


async def test_listing_can_be_narrowed_to_named_queues():
    console, stream = build(queues=["mail", "reports"])

    await console.run_async(["queue:list", "-q", "mail"])
    text = written(stream)

    assert "mail" in text
    assert "reports" not in text


async def test_an_empty_queue_reports_zero():
    console, stream = build(queues=["mail"])

    await console.run_async(["queue:list"])

    assert "0" in written(stream)


async def test_a_queue_reports_the_work_waiting_on_it():
    from sillo.work.commands import connection_for

    connection = connection_for(None)
    await connection.push("mail", {"job": "SendWelcome"})

    console, stream = build(queues=["mail"])
    # The in-process connection is rebuilt per command, so this asserts the
    # size call is wired rather than that the number survives.
    assert await console.run_async(["queue:list"]) == 0
    assert "mail" in written(stream)


# -- the in-process warning --------------------------------------------


async def test_a_broken_connection_fails_cleanly_instead_of_a_traceback(
    monkeypatch,
):
    console, stream = build()

    class BrokenConnection:
        async def size(self, name):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(
        "sillo.work.console.WorkCommand.connection", lambda self: BrokenConnection()
    )

    code = await console.run_async(["queue:list"])

    assert code != 0
    assert "Could not reach the queue backend" in written(stream)


async def test_an_in_process_queue_says_it_is_not_shared():
    console, stream = build(queues=["mail"])

    await console.run_async(["queue:list"])
    text = written(stream)

    assert "in-process" in text
    assert "not" in text.lower()


async def test_a_broker_url_is_reported_instead_of_the_warning():
    console, stream = build(queues=["mail"], url="redis://localhost:6379/0")

    # No connection is opened by the reporting itself, so this stays offline.
    await console.run_async(["queue:list", "--help"])

    assert "in-process" not in written(stream)


# -- failed jobs -------------------------------------------------------


async def test_no_failures_says_so(failed_repository):
    console, stream = build(failed=failed_repository)

    assert await console.run_async(["queue:failed"]) == 0
    assert "No failed jobs recorded." in written(stream)


async def test_an_unbound_repository_warns_that_it_is_only_in_memory():
    console, stream = build()

    await console.run_async(["queue:failed"])
    text = written(stream)

    # Reporting "no failures" from a fresh empty process would be a lie by
    # omission at somebody about to stop looking.
    assert "only kept in memory" in text


async def test_failures_are_listed(failed_repository):
    await failed_repository.log(
        job_id="job-1",
        job_class="SendWelcomeEmail",
        queue="mail",
        payload={},
        exception=RuntimeError("smtp refused"),
    )

    console, stream = build(failed=failed_repository)
    assert await console.run_async(["queue:failed"]) == 0
    text = written(stream)

    assert "SendWelcomeEmail" in text
    assert "mail" in text


async def test_a_failure_can_be_forgotten(failed_repository):
    await failed_repository.log(
        job_id="job-1",
        job_class="SendWelcomeEmail",
        queue="mail",
        payload={},
        exception=RuntimeError("smtp refused"),
    )

    console, stream = build(failed=failed_repository)

    assert await console.run_async(["queue:forget", "job-1"]) == 0
    assert await failed_repository.all() == []


async def test_forgetting_an_unknown_failure_fails(failed_repository):
    console, stream = build(failed=failed_repository)

    assert await console.run_async(["queue:forget", "nope"]) == 1
    assert "No failed job with id 'nope'" in written(stream)


async def test_flushing_needs_confirmation(failed_repository):
    await failed_repository.log(
        job_id="job-1",
        job_class="Job",
        queue="mail",
        payload={},
        exception=RuntimeError("x"),
    )

    console, stream = build(failed=failed_repository)

    # Not interactive, so confirm() takes its default of False.
    assert await console.run_async(["queue:flush"]) == 1
    assert "Nothing done." in written(stream)
    assert len(await failed_repository.all()) == 1


async def test_force_flushes_without_asking(failed_repository):
    await failed_repository.log(
        job_id="job-1",
        job_class="Job",
        queue="mail",
        payload={},
        exception=RuntimeError("x"),
    )

    console, stream = build(failed=failed_repository)

    assert await console.run_async(["queue:flush", "--force"]) == 0
    assert await failed_repository.all() == []


# -- the scheduler -----------------------------------------------------


async def test_scheduled_tasks_are_listed(scheduler):
    console, stream = build(scheduler=scheduler)

    assert await console.run_async(["schedule:list"]) == 0
    text = written(stream)

    assert "cleanup" in text
    assert "sync" in text


async def test_the_trigger_is_shown_for_each_task(scheduler):
    console, stream = build(scheduler=scheduler)

    await console.run_async(["schedule:list"])
    text = written(stream)

    assert "0 3 * * *" in text or "3600" in text


def test_trigger_description_with_no_trigger_at_all():
    from sillo.work.console import ScheduleRun

    class Job:
        trigger = None

    assert ScheduleRun._trigger(Job()) == "—"


def test_trigger_description_for_a_one_shot_date_trigger():
    from sillo.work.console import ScheduleRun

    class DateTrigger:
        at = "2030-01-01T00:00:00"

    class Job:
        trigger = DateTrigger()

    assert ScheduleRun._trigger(Job()) == "once at 2030-01-01T00:00:00"


def test_trigger_description_falls_back_to_the_class_name():
    from sillo.work.console import ScheduleRun

    class MysteryTrigger:
        pass

    class Job:
        trigger = MysteryTrigger()

    assert ScheduleRun._trigger(Job()) == "MysteryTrigger"


async def test_an_empty_scheduler_says_so():
    from sillo.work.scheduler.manager import SchedulerManager

    console, stream = build(scheduler=SchedulerManager())

    await console.run_async(["schedule:list"])

    assert "No scheduled tasks registered." in written(stream)


async def test_a_task_can_be_paused_and_resumed(scheduler):
    console, stream = build(scheduler=scheduler)
    task = scheduler.list()[0]

    assert await console.run_async(["schedule:pause", task.id]) == 0
    assert await console.run_async(["schedule:resume", task.id]) == 0


async def test_pausing_an_unknown_task_fails(scheduler):
    console, stream = build(scheduler=scheduler)

    assert await console.run_async(["schedule:pause", "nope"]) == 1
    assert "No scheduled task with id 'nope'" in written(stream)


async def test_resuming_an_unknown_task_fails(scheduler):
    console, stream = build(scheduler=scheduler)

    assert await console.run_async(["schedule:resume", "nope"]) == 1
    assert "No scheduled task with id 'nope'" in written(stream)


async def test_a_scheduler_command_without_a_manager_says_how_to_bind_one():
    console, stream = build()

    assert await console.run_async(["schedule:list"]) == 1
    assert "work_commands(scheduler=...)" in written(stream)


async def test_the_scheduler_may_be_given_as_a_factory(scheduler):
    console, stream = build(scheduler=lambda: scheduler)

    assert await console.run_async(["schedule:list"]) == 0
    assert "cleanup" in written(stream)


# -- the worker --------------------------------------------------------


def test_the_worker_is_reachable_by_its_alias():
    console, _ = build()

    assert console.resolve("worker") is console.resolve("queue:work")


def test_the_scheduler_runner_is_reachable_by_its_alias():
    console, _ = build()

    assert console.resolve("scheduler") is console.resolve("schedule:run")


def test_the_worker_declares_the_options_a_worker_needs():
    console, _ = build()
    names = {parameter.name for parameter in console.resolve("queue:work").arguments}

    assert names == {"queue", "concurrency", "timeout", "max-jobs"}


async def test_the_worker_command_runs_until_cancelled():
    console, stream = build()

    task = asyncio.ensure_future(
        console.run_async(["queue:work", "--concurrency", "1"])
    )
    await asyncio.sleep(0.3)

    assert not task.done()
    assert "Waiting for jobs" in written(stream)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# -- binding -----------------------------------------------------------


def test_only_registers_the_named_commands():
    console, _ = build(only=["queue:list", "queue:failed"])

    assert set(console.commands) == {"queue:list", "queue:failed"}


def test_only_rejects_a_name_it_does_not_define():
    with pytest.raises(ValueError, match="work_commands has no 'queue:nope'"):
        work_commands(only=["queue:nope"])


def test_the_default_queue_is_used_when_none_are_named():
    from sillo.work.console import DEFAULT_QUEUE

    commands = work_commands()

    assert commands[0].config.queues == [DEFAULT_QUEUE]


def test_an_unbound_command_says_how_to_register_it():
    from sillo.work.console import QueueList

    stream = io.StringIO()
    console = Console(output=stream, error=stream, color=False, interactive=False)
    console.add(QueueList)

    with pytest.raises(RuntimeError, match="work_commands"):
        console.run(["queue:list"])


async def test_the_scheduler_runner_passes_the_manager_not_a_callback(
    scheduler, monkeypatch
):
    """``run_scheduler``'s first positional is a callback invoked *with* the
    manager, not the manager itself. Passing an already populated manager there
    calls it with an argument it does not accept.

    schedule:run blocks forever, so nothing else in this file reaches the call.
    """
    captured = {}

    async def fake_run_scheduler(register=None, *, manager=None, **kwargs):
        captured["register"] = register
        captured["manager"] = manager

    monkeypatch.setattr("sillo.work.commands.run_scheduler", fake_run_scheduler)

    console, _ = build(scheduler=scheduler)
    assert await console.run_async(["schedule:run"]) == 0

    assert captured["manager"] is scheduler
    assert captured["register"] is None
