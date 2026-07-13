"""
sillo.work.queue — Multi-backend, priority-aware task queue.

A ``Queue`` is the entry point for submitting work.  It wraps a backend
(Memory or Redis), adds deduplication, priority routing, middleware,
and completion callbacks.

Usage::

    queue = Queue("emails", backend=MemoryBackend(), dedup=True)
    await queue.put(send_email, "user@ex.com", priority=TaskPriority.HIGH)
    result = await queue.get_result(task.id)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .backends import MemoryBackend
from .task import Task
from .types import (
    QueueFull,
    QueueStats,
    TaskPriority,
    TaskResult,
    TaskRejected,
)

logger = logging.getLogger("sillo.work.queue")


class Queue:
    """Priority-aware, multi-backend task queue.

    The entry point for all background work. Accepts async callables, wraps
    them in :class:`Task` objects, and stores them until a :class:`Worker`
    dequeues and executes them.

    Parameters
    ----------
    name:
        Logical queue name used as a namespace in the backend.
    backend:
        Storage backend. ``MemoryBackend`` for dev, ``RedisBackend`` for prod.
    dedup:
        If True, reject tasks whose ``dedup_key`` was already seen.
    default_priority:
        Priority assigned to tasks that don't specify one explicitly.

    Example::

        queue = Queue("emails", backend=MemoryBackend(), dedup=True)
        task = await queue.put(send_email, "user@ex.com")
        result = await queue.get_result(task.id)
    """

    def __init__(self, name: str = "default", *, backend: Optional[Any] = None, dedup: bool = False, default_priority: TaskPriority = TaskPriority.NORMAL):
        self.name = name
        self._backend = backend or MemoryBackend()
        self._dedup = dedup
        self._default_priority = default_priority
        self._middleware: List[Callable] = []
        self._on_complete: List[Callable[[TaskResult], Awaitable[None]]] = []
        self._closed = False

    # ── configuration ──────────────────────────────────────────────────

    def use(self, middleware) -> "Queue":
        self._middleware.append(middleware)
        return self

    def on_complete(self, callback: Callable[[TaskResult], Awaitable[None]]) -> None:
        self._on_complete.append(callback)

    # ── enqueue ────────────────────────────────────────────────────────

    async def put(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Optional[str] = None,
        priority: Optional[TaskPriority] = None,
        max_attempts: int = 1,
        dedup_key: Optional[str] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Task:
        if self._closed:
            raise RuntimeError(f"Queue '{self.name}' is closed")

        if dedup_key and self._dedup:
            try:
                dup = await self._backend.is_duplicate(self.name, dedup_key)
                if dup:
                    raise TaskRejected(
                        f"Duplicate task '{dedup_key}' rejected",
                        queue_name=self.name,
                    )
            except Exception as exc:
                if isinstance(exc, TaskRejected):
                    raise
                logger.warning(f"Dedup check failed: {exc}")

        task = Task(
            func,
            *args,
            name=name,
            priority=priority if priority is not None else self._default_priority,
            max_attempts=max_attempts,
            queue_name=self.name,
            metadata=metadata,
            timeout=timeout,
            **kwargs,
        )

        for mw in self._middleware:
            try:
                await mw.before_enqueue(task)
            except Exception:
                logger.exception(f"Middleware before_enqueue failed for {task.name}")

        await self._backend.enqueue(task)
        logger.debug(f"Enqueued: {task.name} [{task.id[:8]}] queue={self.name}")
        return task

    # ── dequeue ────────────────────────────────────────────────────────

    async def get(self, timeout: Optional[float] = None) -> Optional[Task]:
        return await self._backend.dequeue(self.name, timeout=timeout)

    # ── result management ──────────────────────────────────────────────

    async def mark_done(self, task: Task) -> None:
        if task.result is None:
            return
        for cb in self._on_complete:
            try:
                await cb(task.result)
            except Exception:
                logger.exception("on_complete callback failed")
        await self._backend.store_result(task.result)

    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        return await self._backend.get_result(task_id)

    # ── stats / lifecycle ──────────────────────────────────────────────

    @property
    async def size(self) -> int:
        return await self._backend.queue_size(self.name)

    async def stats(self) -> QueueStats:
        return await self._backend.queue_stats(self.name)

    async def close(self) -> None:
        self._closed = True

    async def flush(self) -> None:
        if hasattr(self._backend, "flush"):
            await self._backend.flush(self.name)
