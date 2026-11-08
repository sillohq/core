"""Regression coverage for Redis scheduler coordination (#497)."""

import asyncio
import multiprocessing
import time
from unittest.mock import AsyncMock

import fakeredis
import fakeredis.aioredis
import pytest

from sillo import SilloApp
from sillo.cache import MemoryCache, RedisCache, configure_cache, reset_cache_config
from sillo.work import Work
from sillo.work.scheduler import (
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
    JobStatus,
    Scheduler,
    SchedulerManager,
    setup_scheduler,
)
from tests.conftest import requires_redis


@pytest.fixture
async def caches():
    server = fakeredis.FakeServer()
    clients = [fakeredis.aioredis.FakeRedis(server=server) for _ in range(2)]
    try:
        yield [RedisCache(client=client, default_ttl=1) for client in clients]
    finally:
        for client in clients:
            await client.aclose()


@pytest.mark.parametrize(
    "trigger", [CronTrigger("0 2 * * *"), IntervalTrigger(60), DateTrigger(1700000000)]
)
async def test_two_workers_run_once_even_when_the_second_arrives_after_release(
    caches, trigger
):
    calls = []

    async def close_invoices():
        calls.append(1)

    managers = [SchedulerManager(cache=cache) for cache in caches]
    jobs = [
        m.schedule(close_invoices, trigger, name="close-invoices") for m in managers
    ]
    assert jobs[0].id != jobs[1].id  # UUIDs must never be the distributed identity.
    await managers[0]._execute(jobs[0])
    await managers[1]._execute(jobs[1])
    assert calls == [1]
    assert jobs[1]._runs == 0
    assert jobs[0].next_run_time == jobs[1].next_run_time
    if isinstance(trigger, DateTrigger):
        assert jobs[1].status == JobStatus.COMPLETED
    key = caches[0].make_key("scheduler", "close-invoices")
    assert await caches[0]._client.ttl(key) > 604790  # overrides cache default_ttl


async def test_contending_worker_skips_and_later_occurrence_runs(caches, monkeypatch):
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def slow():
        calls.append(1)
        entered.set()
        await finish.wait()

    managers = [SchedulerManager(cache=cache) for cache in caches]
    jobs = [m.schedule(slow, IntervalTrigger(60), name="slow") for m in managers]
    owner = asyncio.create_task(managers[0]._execute(jobs[0]))
    await entered.wait()
    await managers[1]._execute(jobs[1])
    assert jobs[1]._runs == 0
    assert jobs[1].next_run_time > time.time()
    finish.set()
    await owner
    future = time.time() + 61
    monkeypatch.setattr(time, "time", lambda: future)
    await managers[1]._execute(jobs[1])
    assert calls == [1, 1]


async def test_long_job_renews_lease(caches):
    entered, finish = asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await finish.wait()

    manager = SchedulerManager(cache=caches[0], lease=0.3)
    job = manager.schedule(slow, IntervalTrigger(60), name="slow")
    extend = caches[0]._extend_lock
    caches[0]._extend_lock = AsyncMock(wraps=extend)
    owner = asyncio.create_task(manager._execute(job))
    try:
        await entered.wait()
        for _ in range(100):
            if caches[0]._extend_lock.await_count >= 4:
                break
            await asyncio.sleep(0.02)
        assert caches[0]._extend_lock.await_count >= 4
        lock = caches[1].lock(caches[1].make_key("scheduler", "slow"))
        assert not await lock.acquire()
    finally:
        finish.set()
        await owner
    assert await lock.acquire()
    await lock.release()


@pytest.mark.parametrize("failure", [False, RuntimeError("Redis unavailable")])
async def test_lost_or_failed_renewal_cancels_the_job(caches, failure, caplog):
    cancelled = asyncio.Event()

    async def slow():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    caches[0]._extend_lock = AsyncMock(
        return_value=failure, side_effect=failure if failure else None
    )
    manager = SchedulerManager(cache=caches[0], lease=0.03)
    job = manager.schedule(slow, IntervalTrigger(60))
    await asyncio.wait_for(manager._execute(job), timeout=2)
    assert cancelled.is_set()
    assert job.current_instances == 0
    assert "lease" in caplog.text.lower()


@pytest.mark.parametrize("operation", ["_acquire_lock", "get", "set"])
async def test_redis_errors_fail_closed(caches, operation, caplog):
    setattr(caches[0], operation, AsyncMock(side_effect=RuntimeError("Redis down")))
    func = AsyncMock()
    manager = SchedulerManager(cache=caches[0])
    job = manager.schedule(func, IntervalTrigger(60), name="billing")
    await manager._execute(job)
    func.assert_not_awaited()
    assert "Redis down" in caplog.text


@pytest.mark.parametrize("cancel", [False, True])
async def test_failure_and_cancellation_release_lease_without_repeating_fire(
    caches, cancel
):
    async def fails():
        if cancel:
            raise asyncio.CancelledError
        raise ValueError("job failed")

    manager = SchedulerManager(cache=caches[0])
    job = manager.schedule(fails, IntervalTrigger(60), name="billing")
    await manager._execute(job)
    lock = caches[1].lock(caches[1].make_key("scheduler", "billing"))
    assert await lock.acquire()
    await lock.release()
    other = SchedulerManager(cache=caches[1])
    duplicate = other.schedule(fails, IntervalTrigger(60), name="billing")
    await other._execute(duplicate)
    assert duplicate._runs == 0


async def test_shutdown_cancels_running_job_and_releases_lease(caches):
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    manager = SchedulerManager(cache=caches[0])
    job = manager.schedule(slow, IntervalTrigger(60), name="shutdown")
    job.next_run_time = time.time() - 1
    await manager.start()
    await asyncio.wait_for(entered.wait(), 2)
    await manager.stop()
    assert cancelled.is_set()
    assert not manager._tasks
    lock = caches[1].lock(caches[1].make_key("scheduler", "shutdown"))
    assert await lock.acquire()
    await lock.release()


async def test_expired_owner_does_not_block_future_fires(caches):
    key = caches[0].make_key("scheduler", "crashed")
    crashed = caches[0].lock(key, lease=0.01)
    assert await crashed.acquire()
    await asyncio.sleep(0.03)
    manager = SchedulerManager(cache=caches[1])
    func = AsyncMock()
    job = manager.schedule(func, IntervalTrigger(60), name="crashed")
    await manager._execute(job)
    func.assert_awaited_once()
    assert not await crashed.release()


async def test_default_redis_is_selected_at_startup_but_memory_stays_local(caches):
    try:
        for backend, expected in [(caches[0], caches[0]), (MemoryCache(), None)]:
            manager = SchedulerManager()
            configure_cache(backend)  # configuring after installation is supported
            await manager.start()
            assert manager.cache is expected
            await manager.stop()
    finally:
        reset_cache_config()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lease": 0},
        {"lease": float("inf")},
        {"lease": float("nan")},
        {"namespace": ""},
        {"claim_ttl": 0},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        SchedulerManager(**kwargs)


@pytest.mark.parametrize("order", ["scheduler-first", "work-first"])
def test_both_installation_orders_reuse_one_scheduler(order):
    app = SilloApp()
    if order == "scheduler-first":
        scheduler = setup_scheduler(app, cache=MemoryCache(), namespace="billing")
        work = app.install(Work())
    else:
        work = app.install(Work())
        scheduler = app.install(Scheduler())
    assert scheduler is work["scheduler"] is app.state["scheduler"]


async def test_namespaces_and_explicit_ids_are_independent(caches):
    calls = []

    async def same():
        calls.append(1)

    for namespace, job_id in [("one", "a"), ("one", "b"), ("two", "a")]:
        manager = SchedulerManager(cache=caches[0], namespace=namespace)
        await manager._execute(manager.schedule(same, IntervalTrigger(60), id=job_id))
    assert len(calls) == 3


def test_unnamed_identity_is_stable():
    async def same():
        pass

    first, second = SchedulerManager(), SchedulerManager()
    assert (
        first.every(60)(same).coordination_id == second.every(60)(same).coordination_id
    )


def test_cron_advances_past_a_skipped_fire():
    manager = SchedulerManager()
    job = manager.schedule(AsyncMock(), CronTrigger("* * * * *"), name="cron")
    job.last_run_time = time.time() - 180
    now = time.time()
    job.compute_next(now)
    assert job.next_run_time > now


def _process_fire(url, gate, output):
    """Each spawned interpreter owns its scheduler and its Redis connection."""

    async def run():
        cache = RedisCache(url=url, namespace="scheduler-process-test")

        async def invoice():
            output.put("invoice")

        manager = SchedulerManager(cache=cache)
        job = manager.schedule(invoice, DateTrigger(1700000000), name="invoice")
        gate.wait(timeout=10)
        await manager._execute(job)
        await cache.close()

    asyncio.run(run())


@requires_redis
def test_independent_processes_share_one_fire(redis_url):
    ctx = multiprocessing.get_context("spawn")
    gate, output = ctx.Event(), ctx.Queue()
    processes = [
        ctx.Process(target=_process_fire, args=(redis_url, gate, output))
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        gate.set()
        for process in processes:
            process.join(timeout=20)
            assert process.exitcode == 0
        assert output.get(timeout=2) == "invoice"
        import queue

        with pytest.raises(queue.Empty):
            output.get(timeout=0.1)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        output.close()
