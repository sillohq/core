import asyncio
import time

import pytest

from nexios.utils.concurrency import (
    AsyncLazy,
    TaskGroup,
    create_background_task,
    run_in_threadpool,
    run_until_first_complete,
)


# TaskGroup Tests
async def test_task_group_basic():
    results = []
    async with TaskGroup() as group:
        task1 = group.create_task(asyncio.sleep(0.1, result=1))
        task2 = group.create_task(asyncio.sleep(0.2, result=2))

        results.append(await task1)
        results.append(await task2)

    assert results == [1, 2]


async def test_task_group_cancellation():
    async with TaskGroup() as group:
        task = group.create_task(asyncio.sleep(10))
        # Exit context before task completes

    assert task.cancelled()


async def test_task_group_error_propagation():
    with pytest.raises(ValueError):
        async with TaskGroup() as group:
            group.create_task(asyncio.sleep(0.1))
            task2 = group.create_task(raise_error())
            await task2


async def raise_error():
    raise ValueError("Test error")


# Run in ThreadPool Tests
def cpu_bound_task(x: int) -> int:
    time.sleep(0.1)  # Simulate CPU work
    return x * 2


async def test_run_in_threadpool():
    result = await run_in_threadpool(cpu_bound_task, 5)
    assert result == 10


async def test_run_in_threadpool_error():
    with pytest.raises(ValueError):
        await run_in_threadpool(lambda: raise_sync_error())


def raise_sync_error():
    raise ValueError("Sync error")


# Run Until First Complete Tests
async def test_run_until_first_complete():
    async def slow():
        await asyncio.sleep(0.2)
        return "slow"

    async def fast():
        await asyncio.sleep(0.1)
        return "fast"

    result = await run_until_first_complete(slow, fast)
    assert result == "fast"


async def test_create_background_task():
    counter = 0

    async def increment():
        nonlocal counter
        await asyncio.sleep(0.1)
        counter += 1

    task = create_background_task(increment())
    await asyncio.sleep(0.2)
    await task

    assert counter == 1


# AsyncLazy Tests
async def test_async_lazy_computation():
    counter = 0

    async def expensive_operation():
        nonlocal counter
        await asyncio.sleep(0.1)
        counter += 1
        return "result"

    lazy = AsyncLazy(expensive_operation)

    result1 = await lazy.get()
    assert result1 == "result"
    assert counter == 1

    result2 = await lazy.get()
    assert result2 == "result"
    assert counter == 1


async def test_async_lazy_reset():
    counter = 0

    async def expensive_operation():
        nonlocal counter
        counter += 1
        return counter

    lazy = AsyncLazy(expensive_operation)

    result1 = await lazy.get()
    assert result1 == 1

    lazy.reset()
    result2 = await lazy.get()
    assert result2 == 2


async def test_async_lazy_concurrent_access():
    counter = 0

    async def expensive_operation():
        nonlocal counter
        await asyncio.sleep(0.1)
        counter += 1
        return counter

    lazy = AsyncLazy(expensive_operation)

    # Multiple concurrent accesses should result in only one computation
    results = await asyncio.gather(*[lazy.get() for _ in range(5)])

    assert all(r == 1 for r in results)  # All results should be the same
    assert counter == 1


async def test_combined_utilities():
    results = []

    async def process_item(x: int):
        result = await run_in_threadpool(cpu_bound_task, x)
        results.append(result)
        return result  # Return the result for verification

    async with TaskGroup() as group:
        tasks = [group.create_task(process_item(i)) for i in range(5)]
        await asyncio.gather(*tasks)

    lazy_sum = AsyncLazy(lambda: run_in_threadpool(sum, results))

    total = await lazy_sum.get()
    expected = sum(i * 2 for i in range(5))
    assert total == expected, f"Expected {expected}, got {total}, results: {results}"
