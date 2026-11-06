import asyncio
import io
import json

import pytest
from redis.exceptions import ResponseError

fakeredis = pytest.importorskip("fakeredis.aioredis")

from sillo.console import Console
from sillo.work.commands import build_worker
from sillo.work.console import WorkCommand, work_commands
from sillo.work.queue import (
    MemoryFailedRepository,
    RedisConnection,
    RedisFailedRepository,
)
from sillo.work.queue.payloads import PayloadSerializer
from sillo.work.queue.workers import QueueWorker, WorkerOptions


@pytest.fixture
def connection():
    conn = RedisConnection()
    conn._redis = fakeredis.FakeRedis(decode_responses=True)
    return conn


@pytest.mark.asyncio
async def test_failure_survives_new_repository_and_concurrent_retry(connection):
    repo = RedisFailedRepository(connection=connection)
    worker = QueueWorker(None, PayloadSerializer(), repo)
    original = {
        "job": "tests.test_work.work_jobs.NoSuchJob",
        "args": ["order"],
        "attempts": 2,
    }
    job_id = await connection.push("emails", json.dumps(original))
    _, payload = await connection.pop("emails")
    await worker._process_job(
        connection, "emails", {**json.loads(payload), "_job_id": job_id}, 0
    )

    fresh = RedisFailedRepository(connection=connection)
    failure = await fresh.find(job_id)
    assert failure.queue == "emails"
    assert json.loads(failure.payload) == original
    assert [j.id for j in await fresh.all()] == [job_id]
    assert await connection.in_flight("emails") == 0

    results = await asyncio.gather(*(fresh.retry(job_id) for _ in range(8)))
    assert sum(result is not None for result in results) == 1
    assert await fresh.find(job_id) is None
    new_id, retry_payload = await connection.pop("emails")
    assert new_id in results and new_id != job_id
    assert json.loads(retry_payload) == {"job": original["job"], "args": ["order"]}
    assert await connection.pop("emails") is None


@pytest.mark.asyncio
async def test_failed_store_error_keeps_claim_for_recovery(connection):
    repo = RedisFailedRepository(connection=connection)
    worker = QueueWorker(None, PayloadSerializer(), repo)
    payload = json.dumps({"job": "tests.test_work.work_jobs.NoSuchJob"})
    job_id = await connection.push("emails", payload)
    await connection.pop("emails")
    await connection._redis.set(repo.records, "wrong type")
    await worker._process_job(
        connection, "emails", {**json.loads(payload), "_job_id": job_id}, 0
    )
    assert await connection.in_flight("emails") == 1
    _, _, _, claims = connection._keys("emails")
    held = await connection._redis.zrange(claims, 0, -1)
    await connection._redis.zadd(claims, {held[0]: 0})
    assert (await connection.pop("emails"))[0] == job_id


@pytest.mark.asyncio
async def test_retry_enqueue_error_preserves_failure(connection):
    repo = RedisFailedRepository(connection=connection)
    await repo.log("emails", "failed-id", "Job", '{"job":"Job"}', "error")
    await connection._redis.set(connection._keys("emails")[0], "wrong type")
    with pytest.raises(ResponseError):
        await repo.retry("failed-id")
    assert await repo.find("failed-id") is not None


@pytest.mark.asyncio
async def test_failed_repository_pagination_forget_and_flush(connection):
    repo = RedisFailedRepository(connection=connection)
    await repo.log("emails", "one", "Job", "{}", "first")
    await repo.log("emails", "two", "Job", "{}", "second")
    assert await repo.all(limit=0) == []
    assert len(await repo.all(limit=1, offset=1)) == 1
    assert await repo.forget("one") is True
    assert await repo.forget("one") is False
    assert await repo.find("one") is None
    assert [job.id for job in await repo.all()] == ["two"]
    await repo.flush()
    assert await repo.all() == []
    assert await repo.find("two") is None


@pytest.mark.asyncio
async def test_worker_does_not_record_lost_claim(connection, caplog):
    repo = RedisFailedRepository(connection=connection)
    worker = QueueWorker(None, PayloadSerializer(), repo)
    await worker._process_job(
        connection,
        "emails",
        {"job": "tests.test_work.work_jobs.NoSuchJob", "_job_id": "lost"},
        0,
    )
    assert await repo.find("lost") is None
    assert "Lost claim for failed job lost" in caplog.text


@pytest.mark.asyncio
async def test_worker_logs_settlement_error_after_recording(
    connection, monkeypatch, caplog
):
    repo = MemoryFailedRepository()
    worker = QueueWorker(None, PayloadSerializer(), repo)

    async def broken_fail(*args):
        raise RuntimeError("settlement unavailable")

    monkeypatch.setattr(connection, "fail", broken_fail)
    await worker._process_job(
        connection,
        "emails",
        {"job": "tests.test_work.work_jobs.NoSuchJob", "_job_id": "job"},
        0,
    )
    assert (await repo.find("job")).id == "job"
    assert "Failed to settle failed job" in caplog.text


@pytest.mark.asyncio
async def test_console_retry_with_custom_repository(connection, monkeypatch):
    repo = MemoryFailedRepository()
    await repo.log("emails", "failed-id", "Job", '{"job":"Job","attempts":2}', "error")
    monkeypatch.setattr(WorkCommand, "connection", lambda self: connection)
    output = io.StringIO()
    console = Console(output=output, error=output, color=False, interactive=False)
    console.add_many(work_commands(failed=repo))
    assert await console.run_async(["queue:retry", "failed-id"]) == 0
    assert await repo.find("failed-id") is None
    _, payload = await connection.pop("emails")
    assert json.loads(payload) == {"job": "Job"}
    assert await console.run_async(["queue:retry", "failed-id"]) == 1


@pytest.mark.asyncio
async def test_custom_repository_retry_keeps_failure_if_enqueue_fails(
    connection, monkeypatch
):
    repo = MemoryFailedRepository()
    await repo.log("emails", "failed-id", "Job", '{"job":"Job"}', "error")
    monkeypatch.setattr(WorkCommand, "connection", lambda self: connection)
    await connection._redis.set(connection._keys("emails")[0], "wrong type")
    output = io.StringIO()
    console = Console(output=output, error=output, color=False, interactive=False)
    console.add_many(work_commands(failed=repo))
    with pytest.raises(ResponseError):
        await console.run_async(["queue:retry", "failed-id"])
    assert await repo.find("failed-id") is not None


def test_redis_worker_defaults_to_shared_repository(connection):
    worker = build_worker(connection=connection)
    assert isinstance(worker.failed_repo, RedisFailedRepository)
    assert worker.failed_repo.connection is connection


@pytest.mark.asyncio
async def test_console_retries_record_from_another_process(connection, monkeypatch):
    repo = RedisFailedRepository(connection=connection)
    await repo.log("emails", "failed-id", "Job", '{"job":"Job","attempts":2}', "error")

    async def redis_client(self):
        return connection._redis

    monkeypatch.setattr(RedisConnection, "_r", redis_client)
    output = io.StringIO()
    console = Console(output=output, error=output, color=False, interactive=False)
    console.add_many(work_commands(url=connection.url))
    assert await console.run_async(["queue:retry", "failed-id"]) == 0
    assert "Requeued as" in output.getvalue()
    assert await repo.find("failed-id") is None
    _, payload = await connection.pop("emails")
    assert json.loads(payload) == {"job": "Job"}
    assert await console.run_async(["queue:retry", "failed-id"]) == 1


@pytest.mark.asyncio
async def test_worker_consumes_named_queue_on_default_connection(connection):
    worker = build_worker(connection=connection, queues=["emails"], concurrency=1)
    worker.options = WorkerOptions(queues=["emails"], concurrency=1, sleep=0)
    job_id = await connection.push(
        "emails", '{"job":"tests.test_work.work_jobs.NoSuchJob"}'
    )
    process = worker._process_job

    async def process_once(*args):
        await process(*args)
        worker._running = False

    worker._process_job = process_once
    worker._running = True
    await asyncio.wait_for(worker._run_worker(0), timeout=2)
    assert (await worker.failed_repo.find(job_id)).queue == "emails"
