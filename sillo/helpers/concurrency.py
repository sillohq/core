import asyncio
import functools
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")

_threadpool: ThreadPoolExecutor | None = None


def get_threadpool() -> ThreadPoolExecutor:
    """Get Threadpool"""
    global _threadpool
    if _threadpool is None:
        _threadpool = ThreadPoolExecutor()
    return _threadpool


async def run_in_threadpool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run In Threadpool"""
    loop = asyncio.get_running_loop()
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await loop.run_in_executor(get_threadpool(), func, *args)
