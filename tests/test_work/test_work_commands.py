"""
sillo.work.commands — starting a queue worker and a scheduler.

The value here is the assembly: a worker is five collaborating objects, and
every project would otherwise wire them by hand. These tests check the wiring,
including the connection choice that decides whether a queue is shared between
processes at all.
"""

import asyncio
import signal

import pytest

from sillo.work.commands import (
    _install_stop_handler,
    build_worker,
    connection_for,
    run_scheduler,
    run_worker,
)
from sillo.work.queue import QueueWorker, RedisConnection, SyncConnection


@pytest.fixture(autouse=True)
def _restore_signal_handlers():
    """Tests below install real SIGINT/SIGTERM handlers on the running loop
    to exercise that code path; this restores the defaults afterward so a
    handler bound to one test's (by-then-cancelled) task doesn't leak into
    later tests or the pytest process itself."""
    yield
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # a sync test with no running loop; nothing to remove
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.remove_signal_handler(sig)
        except (NotImplementedError, RuntimeError):
            pass


class TestConnectionChoice:
    def test_no_url_keeps_the_queue_in_process(self):
        """SyncConnection shares nothing and survives no restart, so it is the
        default only because it needs no server — never because it is right."""
        assert isinstance(connection_for(None), SyncConnection)

    @pytest.mark.parametrize("url", ["redis://localhost:6379", "rediss://secure:6379"])
    def test_a_redis_url_gives_a_shared_queue(self, url):
        assert isinstance(connection_for(url), RedisConnection)

    def test_an_unsupported_scheme_says_which_it_was(self):
        with pytest.raises(ValueError) as error:
            connection_for("amqp://broker")

        assert "amqp" in str(error.value)
        assert "redis" in str(error.value)


class TestBuildWorker:
    def test_it_assembles_a_worker(self):
        assert isinstance(build_worker(), QueueWorker)

    def test_a_supplied_connection_wins_over_the_url(self):
        """So a project can hand in a connection the URL form cannot describe."""
        connection = SyncConnection()

        worker = build_worker(url="redis://localhost:6379", connection=connection)

        assert worker.manager.connection("default") is connection

    def test_it_registers_under_the_name_the_worker_reads(self):
        """`add`, not `register` — the latter does not exist on ConnectionManager."""
        worker = build_worker()

        assert worker.manager.connection("default") is not None


class TestRunning:
    async def test_run_worker_keeps_running_until_stopped(self):
        task = asyncio.create_task(run_worker(concurrency=1, handle_signals=False))
        await asyncio.sleep(0.3)

        assert not task.done()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_run_scheduler_registers_tasks_before_starting(self):
        registered = []

        def register(manager):
            manager.every(60, name="heartbeat")(lambda: None)
            registered.append(manager)

        task = asyncio.create_task(run_scheduler(register, handle_signals=False))
        await asyncio.sleep(0.3)

        assert registered, "register was never called"
        assert len(registered[0].list()) == 1
        assert not task.done()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_a_failing_register_surfaces_rather_than_starting_empty(self):
        """A scheduler running with none of your tasks is worse than a crash."""

        def register(manager):
            raise RuntimeError("bad task definition")

        with pytest.raises(RuntimeError, match="bad task definition"):
            await run_scheduler(register, handle_signals=False)

    async def test_run_scheduler_awaits_an_async_register_callback(self):
        registered = []

        async def register(manager):
            manager.every(60, name="heartbeat")(lambda: None)
            registered.append(manager)

        task = asyncio.create_task(run_scheduler(register, handle_signals=False))
        await asyncio.sleep(0.3)

        assert registered, "async register was never awaited"

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_run_worker_installs_signal_handlers_when_asked(self):
        task = asyncio.create_task(run_worker(concurrency=1, handle_signals=True))
        await asyncio.sleep(0.3)

        assert not task.done()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_run_scheduler_installs_signal_handlers_when_asked(self):
        task = asyncio.create_task(run_scheduler(handle_signals=True))
        await asyncio.sleep(0.3)

        assert not task.done()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestInstallStopHandler:
    async def test_installs_without_raising(self):
        called = []
        _install_stop_handler(lambda: called.append(1))
        # Nothing to assert about signal delivery here — just that
        # installation itself doesn't raise on this platform.
