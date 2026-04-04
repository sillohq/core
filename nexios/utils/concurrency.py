import asyncio
import functools
import warnings
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
    TypeVar,
)

import anyio

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


async def run_until_first_complete(*args: tuple[Callable, dict]) -> None:  # type: ignore[type-arg]
    warnings.warn(
        "run_until_first_complete is deprecated and will be removed in a future version.",
        DeprecationWarning,
    )

    async with anyio.create_task_group() as task_group:

        async def run(func: Callable[[], Coroutine]) -> None:  # type: ignore[type-arg]
            await func()
            task_group.cancel_scope.cancel()

        for func, kwargs in args:
            task_group.start_soon(run, functools.partial(func, **kwargs))


def create_background_task(
    coro: Coroutine[Any, Any, Any], *, name: Optional[str] = None
) -> asyncio.Task:
    """Create a background task."""
    return asyncio.create_task(coro, name=name)


class AsyncLazy(Generic[T]):
    """Lazy async value that is computed only when needed.

    AsyncLazy provides lazy evaluation with caching for expensive async operations.
    The computation runs only once when first accessed, and subsequent calls return
    the cached result. This is perfect for expensive database aggregations,
    configuration loading, external API calls for reference data, machine learning
    model loading, and file parsing operations.

    The class is thread-safe and uses asyncio.Lock to ensure that the computation
    is only performed once, even if multiple coroutines try to access the value
    simultaneously.

    Attributes:
        func: The async function that computes the value
        _value: The cached computed value (None if not computed yet)
        _lock: Async lock for thread-safe initialization
        _initialized: Flag indicating if the value has been computed

    Example:
        ```python
        from nexios.utils.concurrency import AsyncLazy
        import asyncio

        # Create a lazy-loaded configuration
        config = AsyncLazy(lambda: load_config_from_database())

        async def handler():
            # Value computed only on first access
            cfg = await config.get()
            return cfg

        # Later calls return cached value
        cached_cfg = await config.get()

        # Reset to force recomputation
        config.reset()
        ```
    """

    def __init__(self, func: Callable[[], Awaitable[T]]):
        """Initialize AsyncLazy with an async function.

        Args:
            func: An async callable that returns the value to be cached.
                  The function should take no arguments.

        Example:
            ```python
            # Simple case
            lazy_value = AsyncLazy(lambda: fetch_expensive_data())

            # With lambda wrapping
            lazy_config = AsyncLazy(
                lambda: load_config_with_params("config.yaml")
            )
            ```
        """
        self.func = func
        self._value: Optional[T] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def get(self) -> T:
        """Get the value, computing it if necessary.

        This method ensures that the value is computed only once, even if multiple
        coroutines call it simultaneously. The first caller will trigger the
        computation, while subsequent callers will wait for the computation to
        complete and then return the cached result.

        Returns:
            The computed value of type T.

        Raises:
            Any exception raised by the underlying function during computation.

        Example:
            ```python
            # First call triggers computation
            result1 = await lazy_value.get()

            # Subsequent calls return cached result
            result2 = await lazy_value.get()  # Instant, no recomputation

            assert result1 is result2  # Same cached object
            ```
        """
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._value = await self.func()
                    self._initialized = True
        assert self._value is not None
        return self._value

    def reset(self) -> None:
        """Reset the value so it will be recomputed next time.

        This method clears the cached value and resets the initialization flag.
        The next call to get() will trigger recomputation. This is useful for
        refreshing cached data or when the underlying data source has changed.

        Note: This method is not thread-safe with respect to ongoing get() calls.
        If you need to reset while other coroutines might be accessing the value,
        ensure proper synchronization.

        Example:
            ```python
            # Reset cache periodically
            async def refresh_cache():
                while True:
                    await asyncio.sleep(3600)  # Every hour
                    lazy_config.reset()

            # Reset after data update
            await update_database()
            lazy_stats.reset()  # Force fresh stats on next access
            ```
        """
        self._initialized = False
        self._value = None


class AsyncEvent:
    """An async event that can be used to coordinate coroutines.

    Allows multiple coroutines to wait for an event to be set.
    Useful for shutdown coordination, signaling, and workflow synchronization.

    Example:
        ```python
        event = AsyncEvent()

        async def waiter():
            await event.wait()  # Blocks until set() is called
            print("Event occurred!")

        # In another coroutine:
        event.set()  # Unblocks all waiters
        ```
    """

    def __init__(self):
        """Create a new AsyncEvent in cleared state."""
        self._waiters: List[asyncio.Future] = []
        self._value = False

    def set(self) -> None:
        """Set the event and wake up all waiting coroutines."""
        self._value = True
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(True)
        self._waiters.clear()

    def clear(self) -> None:
        """Clear the event so future wait() calls will block."""
        self._value = False

    async def wait(self) -> bool:
        """Wait for the event to be set. Returns True when event occurs."""
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
