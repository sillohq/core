"""
sillo.work.background.tasks — Fire-and-forget background task with full lifecycle.

A ``BackgroundTask`` launches a coroutine in the background and provides
a handle for waiting, cancelling, inspecting results, and attaching
completion callbacks.  All active tasks are tracked globally for graceful
drain operations.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional, Set

from typing_extensions import Doc

from ..task import Task
from ..types import TaskResult, TaskStatus

logger = logging.getLogger("sillo.work.background")


class BackgroundTask:
    """Fire-and-forget async task with result tracking.

    Launched immediately on construction.  All instances are tracked in a
    class-level set that can be drained before shutdown.

    Usage::

        bt = BackgroundTask.run(send_email, user.email)
        await bt.wait(timeout=30)
        bt.cancel()

        # With completion callback:
        bt = BackgroundTask.run(process_file, path, on_done=notify_user)
    """

    _instances: Set["BackgroundTask"] = set()
    _lock = asyncio.Lock()

    def __init__(
        self,
        func: Annotated[
            Callable[..., Awaitable[Any]], Doc("Async callable to execute.")
        ],
        *args: Annotated[Any, Doc("Positional arguments forwarded to *func*.")],
        name: Annotated[
            Optional[str], Doc("Human-readable label. Defaults to func.__name__.")
        ] = None,
        on_done: Annotated[
            Optional[Callable[[TaskResult], Awaitable[None]]],
            Doc("Callback on completion (success or failure)."),
        ] = None,
        on_success: Annotated[
            Optional[Callable[[TaskResult], Awaitable[None]]],
            Doc("Callback on success only."),
        ] = None,
        on_failure: Annotated[
            Optional[Callable[[TaskResult], Awaitable[None]]],
            Doc("Callback on failure only."),
        ] = None,
        timeout: Annotated[
            Optional[float], Doc("Per-task execution timeout in seconds.")
        ] = None,
        metadata: Annotated[
            Optional[Dict[str, Any]], Doc("Arbitrary metadata for observability.")
        ] = None,
        **kwargs: Annotated[Any, Doc("Keyword arguments forwarded to *func*.")],
    ) -> None:
        """Init

            Args:
                func: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self._task_obj = Task(
            func,
            *args,
            name=name or func.__name__,
            metadata=metadata,
            timeout=timeout,
            **kwargs,
        )
        if on_done:
            self._task_obj.on_success(on_done).on_failure(on_done)
        if on_success:
            self._task_obj.on_success(on_success)
        if on_failure:
            self._task_obj.on_failure(on_failure)
        self._asyncio_task = asyncio.ensure_future(self._task_obj.run())
        self._started_at = time.time()
        BackgroundTask._instances.add(self)

    async def wait(
        self,
        timeout: Annotated[
            Optional[float], Doc("Max seconds to wait. None = forever.")
        ] = None,
    ) -> Any:
        """Block until the task completes and return its result.

        Raises the original exception if the task failed.
        """
        return await self._task_obj.wait(timeout=timeout)

    def cancel(self) -> bool:
        """Cancel the underlying asyncio task. Returns True if cancelled."""
        if self._asyncio_task and not self._asyncio_task.done():
            return self._asyncio_task.cancel()
        return False

    @property
    def done(self) -> bool:
        """True if the task has completed (success, failure, or cancellation)."""
        return self._task_obj.is_done

    @property
    def running(self) -> bool:
        """True if the task is currently executing."""
        return self._task_obj.status == TaskStatus.RUNNING

    @property
    def result(self) -> Optional[TaskResult]:
        """The TaskResult if completed, else None."""
        return self._task_obj.result

    @property
    def id(self) -> str:
        """Unique task identifier."""
        return self._task_obj.id

    @property
    def name(self) -> str:
        """Human-readable task name."""
        return self._task_obj.name

    @property
    def elapsed(self) -> float:
        """Seconds since the task was launched."""
        return time.time() - self._started_at

    def to_dict(self) -> Dict[str, Any]:
        """Serialise task metadata for monitoring."""
        return {
            "id": self.id,
            "name": self.name,
            "done": self.done,
            "running": self.running,
            "elapsed": self.elapsed,
            "status": self._task_obj.status.value,
            "result": self.result.to_dict() if self.result else None,
        }

    @classmethod
    def run(
        cls,
        func: Annotated[Callable[..., Awaitable[Any]], Doc("Async callable.")],
        *args: Annotated[Any, Doc("Positional arguments.")],
        **kwargs: Annotated[Any, Doc("Keyword arguments.")],
    ) -> "BackgroundTask":
        """Create and immediately start a background task.

        Must be called from within an async context (running event loop).
        Raises :exc:`RuntimeError` if called outside an async context.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError("BackgroundTask.run() requires an async context")
        return cls(func, *args, **kwargs)

    @classmethod
    def run_sync(
        cls,
        func: Annotated[Callable[..., Any], Doc("Sync or async callable.")],
        *args: Annotated[Any, Doc("Positional arguments.")],
        **kwargs: Annotated[Any, Doc("Keyword arguments.")],
    ) -> "BackgroundTask":
        """Create a background task, auto-wrapping sync functions."""
        if not inspect.iscoroutinefunction(func):

            async def _wrapper(*a, **kw):
                """Wrapper

                    Returns:
                        [description]

                    Raises:
                        [description]
                """
                return func(*a, **kw)

            return cls(_wrapper, *args, **kwargs)
        return cls(func, *args, **kwargs)

    @classmethod
    async def drain(
        cls,
        timeout: Annotated[float, Doc("Max seconds to wait for all tasks.")] = 10.0,
        cancel_remaining: Annotated[
            bool, Doc("Cancel tasks that don't finish in time.")
        ] = True,
    ) -> Dict[str, Any]:
        """Wait for all tracked background tasks to complete.

        Returns a summary dict of completed/cancelled counts.
        """
        instances = list(cls._instances)
        if not instances:
            return {"total": 0, "completed": 0, "cancelled": 0}

        tasks = [i._asyncio_task for i in instances]
        done, pending = await asyncio.wait(tasks, timeout=timeout)

        cancelled = 0
        if cancel_remaining and pending:
            for t in pending:
                t.cancel()
            cancelled = len(pending)

        return {
            "total": len(instances),
            "completed": len(done) - cancelled,
            "cancelled": cancelled,
        }

    @classmethod
    def count(cls) -> Dict[str, int]:
        """Return counts of tracked tasks by status."""
        total = len(cls._instances)
        running = sum(1 for t in cls._instances if t.running)
        done = sum(1 for t in cls._instances if t.done)
        return {
            "total": total,
            "running": running,
            "done": done,
            "pending": total - running - done,
        }

    def __repr__(self) -> str:
        """Repr

            Returns:
                [description]

            Raises:
                [description]
        """
        return f"BackgroundTask({self.name}, done={self.done})"
