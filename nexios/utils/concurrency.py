import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar("T")


class TaskGroup:
    """A group of tasks that can be managed together."""

    def __init__(self):
        self.tasks: Set[asyncio.Task] = set()
        self._closed = False

    def create_task(self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        """Create a task in this group."""
        if self._closed:
            raise RuntimeError("TaskGroup is closed")
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def cancel_all(self) -> None:
        """Cancel all tasks in the group."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self._closed = True

    async def __aenter__(self) -> "TaskGroup":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.cancel_all()


@asynccontextmanager
async def create_task_group() -> AsyncGenerator[TaskGroup, None]:
    """Create a task group context manager."""
    async with TaskGroup() as group:
        yield group


_threadpool: Optional[ThreadPoolExecutor] = None


def get_threadpool() -> ThreadPoolExecutor:
    """Get the global threadpool executor."""
    global _threadpool
    if _threadpool is None:
        _threadpool = ThreadPoolExecutor()
    return _threadpool


async def run_in_threadpool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a function in a thread pool."""
    loop = asyncio.get_running_loop()
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await loop.run_in_executor(get_threadpool(), func, *args)


async def run_until_first_complete(
    *args: Union[
        Tuple[Callable[[], Coroutine[Any, Any, T]], dict[Any, Any]],
        Callable[[], Coroutine[Any, Any, T]],
    ],
) -> T:
    """Run multiple coroutines and return when the first one completes."""
    tasks: List[asyncio.Task[Any]] = []
    for item in args:
        if callable(item):
            task = asyncio.create_task(item())
        else:
            func, kwargs = item
            task = asyncio.create_task(func(**kwargs))
        tasks.append(task)
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        # Get the result or raise exception from the first completed task
        result = next(iter(done)).result()
    finally:
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    return result


def create_background_task(
    coro: Coroutine[Any, Any, Any], *, name: Optional[str] = None
) -> asyncio.Task:
    """Create a background task."""
    return asyncio.create_task(coro, name=name)


class AsyncLazy(Generic[T]):
    """Lazy async value that is computed only when needed."""

    def __init__(self, func: Callable[[], Awaitable[T]]):
        self.func = func
        self._value: Optional[T] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def get(self) -> T:
        """Get the value, computing it if necessary."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._value = await self.func()
                    self._initialized = True
        assert self._value is not None
        return self._value

    def reset(self) -> None:
        """Reset the value so it will be recomputed next time."""
        self._initialized = False
        self._value = None


class AsyncEvent:
    """An async event that can be used to coordinate coroutines."""

    def __init__(self):
        self._waiters: List[asyncio.Future] = []
        self._value = False

    def set(self) -> None:
        """Set the event."""
        self._value = True
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(True)
        self._waiters.clear()

    def clear(self) -> None:
        """Clear the event."""
        self._value = False

    async def wait(self) -> bool:
        """Wait for the event to be set."""
        if self._value:
            return True
        waiter = asyncio.Future()
        self._waiters.append(waiter)
        try:
            await waiter
        finally:
            try:
                self._waiters.remove(waiter)
            except ValueError:
                pass
        return True
