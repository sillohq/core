"""Deep tests for sillo.work MemoryBackend (in-process task queue)."""

import asyncio

import pytest

from sillo.work.backends import MemoryBackend
from sillo.work.task import Task
from sillo.work.types import QueueFull, QueueStats, TaskPriority, TaskStatus


async def _noop():
    return "ok"


async def test_enqueue_dequeue_roundtrip():
    b = MemoryBackend()
    t = Task(_noop, name="t1")
    await b.enqueue(t)
    got = await b.dequeue("default")
    assert got is not None
    assert got.id == t.id


async def test_priority_ordering_higher_first():
    b = MemoryBackend()
    low = Task(_noop, name="low", priority=TaskPriority.LOW)
    crit = Task(_noop, name="crit", priority=TaskPriority.CRITICAL)
    norm = Task(_noop, name="norm", priority=TaskPriority.NORMAL)
    # enqueue out of order
    await b.enqueue(low)
    await b.enqueue(norm)
    await b.enqueue(crit)
    order = []
    for _ in range(3):
        t = await b.dequeue("default")
        order.append(t.name)
    assert order == ["crit", "norm", "low"]


async def test_dequeue_respects_created_at_within_same_priority():
    b = MemoryBackend()
    first = Task(_noop, name="a", priority=TaskPriority.HIGH)
    await asyncio.sleep(0.01)
    second = Task(_noop, name="b", priority=TaskPriority.HIGH)
    await b.enqueue(first)
    await b.enqueue(second)
    got1 = await b.dequeue("default")
    got2 = await b.dequeue("default")
    assert got1.id == first.id
    assert got2.id == second.id


async def test_dequeue_blocks_until_available():
    b = MemoryBackend()
    # No task yet; dequeue with a short timeout should return None, then
    # a concurrent producer makes one available.
    async def producer():
        await asyncio.sleep(0.05)
        await b.enqueue(Task(_noop, name="late"))

    start = asyncio.get_event_loop().time()
    prod = asyncio.create_task(producer())
    got = await b.dequeue("default", timeout=1.0)
    elapsed = asyncio.get_event_loop().time() - start
    await prod
    assert got is not None
    assert got.name == "late"
    assert elapsed >= 0.05


async def test_dequeue_timeout_returns_none():
    b = MemoryBackend()
    got = await b.dequeue("default", timeout=0.05)
    assert got is None


async def test_result_storage_and_lookup():
    b = MemoryBackend()
    t = Task(_noop, name="r")
    t.status = TaskStatus.COMPLETED
    from sillo.work.types import TaskResult

    result = TaskResult(
        task_id=t.id, name="r", status=TaskStatus.COMPLETED, result="ok"
    )
    await b.store_result(result)
    fetched = await b.get_result(t.id)
    assert fetched is not None
    assert fetched.result == "ok"
    assert fetched.ok is True


async def test_queue_stats_counts_completed_and_failed():
    b = MemoryBackend()
    from sillo.work.types import TaskResult

    ok = TaskResult(
        task_id="a", name="a", status=TaskStatus.COMPLETED, queue_name="default"
    )
    fail = TaskResult(
        task_id="b", name="b", status=TaskStatus.FAILED, queue_name="default"
    )
    await b.store_result(ok)
    await b.store_result(fail)
    stats = await b.queue_stats("default")
    assert isinstance(stats, QueueStats)
    assert stats.completed == 1
    assert stats.failed == 1


async def test_dedup_tracks_keys_per_queue():
    b = MemoryBackend()
    assert await b.is_duplicate("default", "k1") is False
    assert await b.is_duplicate("default", "k1") is True
    # different queue is independent
    assert await b.is_duplicate("other", "k1") is False
    await b.clear_dedup("default", "k1")
    assert await b.is_duplicate("default", "k1") is False


async def test_queue_size_and_full_limit():
    b = MemoryBackend(max_size=2)
    await b.enqueue(Task(_noop, name="1"))
    await b.enqueue(Task(_noop, name="2"))
    assert await b.queue_size("default") == 2
    with pytest.raises(QueueFull):
        await b.enqueue(Task(_noop, name="3"))


async def test_queue_size_zero_when_empty():
    b = MemoryBackend()
    assert await b.queue_size("default") == 0
