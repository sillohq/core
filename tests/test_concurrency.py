import time

import pytest

from sillo.utils.concurrency import run_in_threadpool


async def test_run_in_threadpool():
    def cpu_bound_task(x: int) -> int:
        time.sleep(0.1)
        return x * 2

    result = await run_in_threadpool(cpu_bound_task, 5)
    assert result == 10


async def test_run_in_threadpool_with_kwargs():
    def greet(greeting: str, name: str) -> str:
        time.sleep(0.05)
        return f"{greeting}, {name}!"

    result = await run_in_threadpool(greet, greeting="Hello", name="World")
    assert result == "Hello, World!"


async def test_run_in_threadpool_error():
    def raise_sync_error():
        raise ValueError("Sync error")

    with pytest.raises(ValueError, match="Sync error"):
        await run_in_threadpool(raise_sync_error)


async def test_multiple_threadpool_calls():
    def compute(x: int) -> int:
        time.sleep(0.05)
        return x * x

    results = []
    for i in range(1, 6):
        r = await run_in_threadpool(compute, i)
        results.append(r)
    assert results == [1, 4, 9, 16, 25]
