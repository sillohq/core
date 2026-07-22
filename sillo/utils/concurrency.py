import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

_threadpool: Optional[ThreadPoolExecutor] = None


def get_threadpool() -> ThreadPoolExecutor:
    """Get Threadpool

        Returns:
            [description]

        Raises:
            [description]
    """
    global _threadpool
    if _threadpool is None:
        _threadpool = ThreadPoolExecutor()
    return _threadpool


async def run_in_threadpool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run In Threadpool

        Args:
            func: [description]

        Returns:
            [description]

        Raises:
            [description]
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await loop.run_in_executor(get_threadpool(), func, *args)
