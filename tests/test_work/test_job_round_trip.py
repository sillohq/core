"""
A dispatched job must come back out of the queue and run.

The two halves used to disagree: dispatch wrote ``{"job": "Greet"}`` while the
worker required ``module.Class`` and raised on anything without a dot. Every job
therefore failed with "Cannot resolve job class", and nothing caught it because
a worker with an empty queue starts, idles and stops perfectly well.

These tests put a job in and assert it ran.
"""

import asyncio

import pytest

from sillo.work.commands import build_worker
from sillo.work.queue import Job, SyncConnection

#: Set by the jobs below, so a test can see that `handle` actually ran.
RAN: list = []


class Greet(Job):
    async def handle(self):
        RAN.append(("Greet", self.__dict__.get("args")))


class Sweep(Job):
    async def handle(self):
        RAN.append(("Sweep", None))


@pytest.fixture(autouse=True)
def _clear():
    RAN.clear()
    yield
    RAN.clear()


async def _drain(connection, queues=("default",), seconds=2.0):
    """Run a worker against *connection* until it has had time to work."""
    worker = build_worker(connection=connection, queues=list(queues), concurrency=2)
    task = asyncio.create_task(worker.run())
    try:
        for _ in range(int(seconds * 20)):
            await asyncio.sleep(0.05)
            if RAN:
                break
    finally:
        worker.stop()
        task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await task
    return RAN


class TestJobReference:
    def test_a_job_names_where_it_can_be_imported_from(self):
        """A bare class name tells a separate worker process nothing."""
        assert Greet.job_reference() == f"{Greet.__module__}.Greet"

    def test_the_payload_carries_that_reference(self):
        import json

        payload = json.loads(Greet._encode_payload((1,), {"b": 2}))

        assert payload["job"] == Greet.job_reference()
        assert "." in payload["job"]


class TestResolution:
    def test_a_qualified_name_is_imported(self):
        worker = build_worker(connection=SyncConnection())

        assert worker._resolve_job_class(Greet.job_reference()) is Greet

    def test_a_bare_name_still_resolves(self):
        """Payloads queued by an older release are already in people's queues."""
        worker = build_worker(connection=SyncConnection())

        assert worker._resolve_job_class("Sweep") is Sweep

    def test_an_unknown_name_says_what_would_fix_it(self):
        worker = build_worker(connection=SyncConnection())

        with pytest.raises(RuntimeError) as caught:
            worker._resolve_job_class("NeverImported")

        assert "Import it" in str(caught.value)


class TestRoundTrip:
    async def test_a_dispatched_job_runs(self):
        """The whole point, and what nothing checked before."""
        connection = SyncConnection()
        Job.on_connection(connection)

        await Greet.dispatch("ada")
        ran = await _drain(connection)

        assert [name for name, _ in ran] == ["Greet"]

    async def test_it_runs_in_the_process_that_dispatched_it(self):
        """Sharing one connection is what lets an application run its own
        worker instead of a second process."""
        connection = SyncConnection()
        Job.on_connection(connection)

        await Sweep.dispatch()
        ran = await _drain(connection)

        assert ("Sweep", None) in ran


class Echo(Job):
    def __init__(self, name="<<default>>", loud=False):
        self.name = name
        self.loud = loud

    async def handle(self):
        RAN.append(("Echo", self.name, self.loud))


class TestArgumentsSurvive:
    """A job that runs with the wrong data is worse than one that fails.

    ``dispatch`` records the call as ``args``/``kwargs``; the worker used to
    rebuild the job from ``data``, which dispatch never writes. Every job was
    constructed with no arguments, ran its defaults, and reported success.
    """

    async def test_positional_arguments_arrive(self):
        connection = SyncConnection()
        Job.on_connection(connection)

        await Echo.dispatch("ada")
        ran = await _drain(connection)

        assert ("Echo", "ada", False) in ran

    async def test_keyword_arguments_arrive(self):
        connection = SyncConnection()
        Job.on_connection(connection)

        await Echo.dispatch(name="ada", loud=True)
        ran = await _drain(connection)

        assert ("Echo", "ada", True) in ran

    def test_the_older_payload_shape_still_builds(self):
        """`Job.payload()` writes attributes under `data`; those may be queued."""
        worker = build_worker(connection=SyncConnection())

        job = worker._build_job(Echo, {"data": {"name": "bob", "loud": True}})

        assert (job.name, job.loud) == ("bob", True)

    def test_a_dispatch_payload_wins_over_data(self):
        worker = build_worker(connection=SyncConnection())

        job = worker._build_job(Echo, {"args": ["carol"], "kwargs": {}})

        assert job.name == "carol"
