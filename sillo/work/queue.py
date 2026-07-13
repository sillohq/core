"""
sillo.work.queue — Multi-backend, priority-aware task queue.

A ``Queue`` is the entry point for submitting background work.  It wraps
a storage backend, adds deduplication, priority routing, and middleware
composition.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional

from typing_extensions import Doc

from .backends import MemoryBackend
from .task import Task
from .types import QueueStats, TaskPriority, TaskResult, TaskRejected

logger = logging.getLogger("sillo.work.queue")


class Queue:
    """Priority-aware, multi-backend task queue.

    Accepts async callables, wraps them in :class:`Task` objects, and
    stores them until a :class:`Worker` dequeues and executes them.

    Usage::

        queue = Queue("emails", backend=MemoryBackend())
        task = await queue.put(send_email, "user@ex.com")
    """

    def __init__(
        self,
<<<<<<< Updated upstream
        name: str = "default",
        *,
        backend: Optional[Any] = None,
        dedup: bool = False,
        default_priority: TaskPriority = TaskPriority.NORMAL,
=======
        name: Annotated[str, Doc("Logical queue name used as a namespace in the backend.")] = "default",
        *,
        backend: Annotated[Optional[Any], Doc("Storage backend. ``MemoryBackend`` for dev, ``RedisBackend`` for prod.")] = None,
        dedup: Annotated[bool, Doc("If True, reject tasks whose ``dedup_key`` was already seen.")] = False,
        default_priority: Annotated[TaskPriority, Doc("Priority for tasks without explicit priority.")] = TaskPriority.NORMAL,
>>>>>>> Stashed changes
    ):
        self.name = name
        self._backend = backend or MemoryBackend()
        self._dedup = dedup
        self._default_priority = default_priority
        self._middleware: List[Callable] = []
        self._on_complete: List[Callable[[TaskResult], Awaitable[None]]] = []
        self._closed = False

    def use(
        self,
        middleware: Annotated[Any, Doc("Middleware object with before_enqueue / before_execute / after_execute / on_error hooks.")],
    ) -> "Queue":
        """Attach middleware that wraps every task execution on this queue.

        Returns self for chaining: ``queue.use(TimeoutMiddleware(30)).use(RateLimitMiddleware(10))``.
        """
        self._middleware.append(middleware)
        return self

    def on_complete(
        self,
        callback: Annotated[Callable[[TaskResult], Awaitable[None]], Doc("Async callback receiving the final TaskResult.")],
    ) -> None:
        """Register a callback fired every time a task completes (success or failure)."""
        self._on_complete.append(callback)

    async def put(
        self,
        func: Annotated[Callable[..., Awaitable[Any]], Doc("Async callable to execute.")],
        *args: Annotated[Any, Doc("Positional arguments forwarded to *func*.")],
        name: Annotated[Optional[str], Doc("Human-readable task name. Defaults to ``func.__name__``.")] = None,
        priority: Annotated[Optional[TaskPriority], Doc("Dequeue priority. Higher values dequeue first.")] = None,
        max_attempts: Annotated[int, Doc("How many times to retry on failure. 1 = no retry.")] = 1,
        dedup_key: Annotated[Optional[str], Doc("If ``dedup=True`` on the queue, reject tasks with a duplicate key.")] = None,
        timeout: Annotated[Optional[float], Doc("Per-task execution timeout in seconds.")] = None,
        metadata: Annotated[Optional[Dict[str, Any]], Doc("Arbitrary dict attached to TaskResult for observability.")] = None,
        **kwargs: Annotated[Any, Doc("Additional keyword arguments forwarded to *func*.")],
    ) -> Task:
        """Enqueue an async callable for later execution.

        Returns a :class:`Task` handle immediately.  The task has NOT
        executed — a :class:`Worker` must pull and run it.

        Raises :exc:`TaskRejected` if the queue is closed or the dedup
        key has already been seen.
        """
        if self._closed:
            raise RuntimeError(f"Queue '{self.name}' is closed")

        if dedup_key and self._dedup:
            try:
                dup = await self._backend.is_duplicate(self.name, dedup_key)
                if dup:
                    raise TaskRejected(f"Duplicate task '{dedup_key}' rejected", queue_name=self.name)
            except Exception as exc:
                if isinstance(exc, TaskRejected):
                    raise
                logger.warning(f"Dedup check failed: {exc}")

        task = Task(
            func, *args, name=name,
            priority=priority if priority is not None else self._default_priority,
            max_attempts=max_attempts, queue_name=self.name,
            metadata=metadata, timeout=timeout, **kwargs,
        )

        for mw in self._middleware:
            try:
                await mw.before_enqueue(task)
            except Exception:
                logger.exception(f"Middleware before_enqueue failed for {task.name}")

        await self._backend.enqueue(task)
        logger.debug(f"Enqueued: {task.name} [{task.id[:8]}] queue={self.name}")
        return task

    async def get(
        self,
        timeout: Annotated[Optional[float], Doc("Seconds to block waiting for a task. None = block indefinitely.")] = None,
    ) -> Optional[Task]:
        """Dequeue the next task, blocking up to *timeout* seconds."""
        return await self._backend.dequeue(self.name, timeout=timeout)

    async def mark_done(
        self,
        task: Annotated[Task, Doc("The completed task to finalise.")],
    ) -> None:
        """Store the task result, fire completion callbacks, and persist to backend."""
        if task.result is None:
            return
        for cb in self._on_complete:
            try:
                await cb(task.result)
            except Exception:
                logger.exception("on_complete callback failed")
        await self._backend.store_result(task.result)

    async def get_result(
        self,
        task_id: Annotated[str, Doc("The task UUID to look up.")],
    ) -> Optional[TaskResult]:
        """Retrieve a previously stored TaskResult by ID."""
        return await self._backend.get_result(task_id)

    @property
    async def size(self) -> int:
        """Number of pending tasks in the queue."""
        return await self._backend.queue_size(self.name)

    async def stats(self) -> QueueStats:
        """Return current :class:`QueueStats` snapshot."""
        return await self._backend.queue_stats(self.name)

    async def close(self) -> None:
        """Reject all future ``put()`` calls."""
        self._closed = True

    async def flush(self) -> None:
        """Discard all pending tasks (Redis backend only)."""
        if hasattr(self._backend, "flush"):
            await self._backend.flush(self.name)
