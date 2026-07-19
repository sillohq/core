"""Deep tests for sillo.work QueueWorker end-to-end consumption,
WorkerOptions, WorkerPool, and MemoryFailedRepository.
"""

import asyncio
import json

import pytest

from sillo.work.queue.connection import ConnectionManager, SyncConnection
from sillo.work.queue.failed import FailedJob, MemoryFailedRepository
from sillo.work.queue.payloads import PayloadSerializer
from sillo.work.queue.workers import QueueWorker, WorkerOptions, WorkerPool
from tests.work.work_jobs import FLIGHTS, SENT_EMAILS, SendEmail


async def test_worker_consumes_job_and_runs_handle():
    SENT_EMAILS.clear()
    mgr = ConnectionManager()
    conn = SyncConnection()
    mgr.add("default", conn)
    ser = PayloadSerializer()
    repo = MemoryFailedRepository()
    worker = QueueWorker(
        mgr,
        ser,
        repo,
        options=WorkerOptions(concurrency=1, sleep=0.05, queues=["default"]),
    )

    payload = json.dumps(
        {
            "job": "tests.work.work_jobs.SendEmail",
            "data": {"to": "end@to.end", "subject": "E2E"},
        }
    )
    await conn.push("default", payload)

    task = asyncio.create_task(worker.run())
    # wait until the job side-effect is observed
    for _ in range(100):
        if SENT_EMAILS:
            break
        await asyncio.sleep(0.02)
    worker.stop()
    await task

    assert SENT_EMAILS == ["end@to.end:E2E"]
    assert len(await repo.all()) == 0


async def test_worker_logs_failed_jobs():
    mgr = ConnectionManager()
    conn = SyncConnection()
    mgr.add("default", conn)
    ser = PayloadSerializer()
    repo = MemoryFailedRepository()
    worker = QueueWorker(
        mgr,
        ser,
        repo,
        options=WorkerOptions(concurrency=1, sleep=0.05, queues=["default"]),
    )

    # A job class that does not exist -> resolution failure -> logged
    import json

    payload = json.dumps({"job": "tests.work.work_jobs.NoSuchJob", "data": {}})
    await conn.push("default", payload)

    task = asyncio.create_task(worker.run())
    for _ in range(100):
        if len(await repo.all()) > 0:
            break
        await asyncio.sleep(0.02)
    worker.stop()
    await task

    failed = (await repo.all())[0]
    assert isinstance(failed, FailedJob)
    assert failed.job_class == "tests.work.work_jobs.NoSuchJob"
    assert failed.exception
    assert isinstance(failed.id, str) and failed.id


async def test_worker_pause_resume_stops_consumption():
    mgr = ConnectionManager()
    conn = SyncConnection()
    mgr.add("default", conn)
    ser = PayloadSerializer()
    repo = MemoryFailedRepository()
    worker = QueueWorker(
        mgr,
        ser,
        repo,
        options=WorkerOptions(concurrency=1, sleep=0.05, queues=["default"]),
    )
    SENT_EMAILS.clear()
    payload = json.dumps(
        {
            "job": "tests.work.work_jobs.SendEmail",
            "data": {"to": "p@u", "subject": "P"},
        }
    )
    await conn.push("default", payload)

    task = asyncio.create_task(worker.run())
    worker.pause()
    await asyncio.sleep(0.15)
    assert SENT_EMAILS == []  # paused: nothing consumed
    worker.resume()
    for _ in range(100):
        if SENT_EMAILS:
            break
        await asyncio.sleep(0.02)
    worker.stop()
    await task
    assert SENT_EMAILS == ["p@u:P"]


async def test_worker_pool_runs_multiple_workers():
    FLIGHTS.clear()
    mgr = ConnectionManager()
    conn = SyncConnection()
    mgr.add("default", conn)
    ser = PayloadSerializer()
    repo = MemoryFailedRepository()
    pool = WorkerPool()
    for _ in range(2):
        pool.add(
            QueueWorker(
                mgr,
                ser,
                repo,
                options=WorkerOptions(concurrency=1, sleep=0.05, queues=["default"]),
            )
        )
    for i in range(3):
        await conn.push(
            "default",
            json.dumps(
                {
                    "job": "tests.work.work_jobs.RecordFlight",
                    "data": {"flight": f"F{i}"},
                }
            ),
        )
    await pool.start()
    for _ in range(150):
        if len(FLIGHTS) >= 3:
            break
        await asyncio.sleep(0.02)
    await pool.shutdown()
    assert set(FLIGHTS) == {"F0", "F1", "F2"}


def test_memory_failed_repository_store_and_clear():
    repo = MemoryFailedRepository()
    import asyncio

    asyncio.run(repo.log("default", "j1", "MyJob", "{}", "boom"))
    assert len(asyncio.run(repo.all())) == 1
    assert asyncio.run(repo.all())[0].id == "j1"
    asyncio.run(repo.flush())
    assert len(asyncio.run(repo.all())) == 0
