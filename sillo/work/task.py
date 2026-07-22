"""
sillo.work.task —  Task lifecycle, callbacks, and serialisation.

A ``Task`` is the smallest schedulable unit of work.  It wraps an async
callable, tracks its execution attempt-by-attempt, fires before/after
hooks, and can be serialised for cross-process transfer.

Callbacks
---------
Callbacks are registered *on the task instance* before the queue hands
it to a worker.  They receive the :class:`~sillo.work.types.TaskResult`
and fire asynchronously.  Exceptions in callbacks are logged but never
propagated — a broken callback must not take down the worker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from uuid import uuid4

from .types import (
    TaskCancelled,
    TaskError,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskTimeout,
)

logger = logging.getLogger("sillo.work.task")


class Task:
    """Single async unit of work.

    Tasks are created by :meth:`Queue.put` or directly by user code.
    Once enqueued, a :class:`Worker` picks them up, calls :meth:`run`,
    and marks completion via the queue.

    Parameters
    ----------
    func:
        Async callable.  Return value becomes ``TaskResult.result``.
    *args, **kwargs:
        Forwarded to *func* on execution.
    name:
        Human-readable label (defaults to ``func.__name__``).
    priority:
        :class:`TaskPriority` — determines dequeue order.
    max_attempts:
        How many times the worker will retry on failure (default 1 = no retry).
    queue_name:
        Logical queue this task belongs to.
    metadata:
        Arbitrary key-value dict attached to the result for observability.
    timeout:
        Per-task execution timeout in seconds.  If elapsed, the task is
        cancelled and the attempt counts as a failure.

    Hooks
    -----
    .. code-block:: python

        task = Task(send_email, email)
        task.before(lambda t: log.info("starting %s", t.name))
        task.after(lambda t: metrics.record(t.result))
        task.on_success(notify_user)
        task.on_failure(log_error)

    The *before* hooks fire synchronously (awaited in order) before the
    core function.  *after* hooks fire in a ``finally`` block — even if
    an exception or cancellation occurred.
    """

    __slots__ = (
        "id",
        "name",
        "func",
        "args",
        "kwargs",
        "status",
        "priority",
        "max_attempts",
        "queue_name",
        "metadata",
        "timeout",
        "result",
        "_task",
        "_done",
        "created_at",
        "started_at",
        "completed_at",
        "attempt",
        "_hooks",
    )

    def __init__(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_attempts: int = 1,
        queue_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Init

        Args:
            func: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.id: str = str(uuid4())
        self.name: str = name or getattr(func, "__name__", "unknown")
        self.func: Callable[..., Awaitable[Any]] = func
        self.args: tuple = args
        self.kwargs: Dict[str, Any] = kwargs
        self.status: TaskStatus = TaskStatus.PENDING
        self.priority: TaskPriority = priority
        self.max_attempts: int = max(1, max_attempts)
        self.queue_name: str = queue_name
        self.metadata: Dict[str, Any] = metadata or {}
        self.timeout: Optional[float] = timeout

        # Internal state
        self.result: Optional[TaskResult] = None
        self._task: Optional[asyncio.Task] = None
        self._done: asyncio.Event = asyncio.Event()
        self.created_at: float = time.time()
        self.started_at: float = 0.0
        self.completed_at: float = 0.0
        self.attempt: int = 0

        # Hook lists — appended to via .before() / .after() / .on_success() / .on_failure()
        self._hooks: Dict[str, List[Callable]] = {
            "before": [],
            "after": [],
            "success": [],
            "failure": [],
        }

    # ── public API ─────────────────────────────────────────────────────────

    @property
    def is_done(self) -> bool:
        """Is Done

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    @property
    def is_running(self) -> bool:
        """Is Running

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.status == TaskStatus.RUNNING

    def before(self, callback: Callable[["Task"], Awaitable[None]]) -> "Task":
        """Before

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._hooks["before"].append(callback)
        return self

    def after(self, callback: Callable[["Task"], Awaitable[None]]) -> "Task":
        """After

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._hooks["after"].append(callback)
        return self

    def on_success(self, callback: Callable[[TaskResult], Awaitable[None]]) -> "Task":
        """On Success

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._hooks["success"].append(callback)
        return self

    def on_failure(self, callback: Callable[[TaskResult], Awaitable[None]]) -> "Task":
        """On Failure

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._hooks["failure"].append(callback)
        return self

    def then(self, next_task: "Task") -> "Task":
        """Chain *next_task* to run after this one completes successfully.

        If this task fails, *next_task* is NOT executed.
        """

        async def _chain(result: TaskResult) -> None:
            """Chain

            Args:
                result: [description]

            Returns:
                [description]

            Raises:
                [description]
            """
            pass  # The queue/worker handles chaining

        self.on_success(_chain)
        self.metadata["_chain"] = next_task.serialize()
        return self

    def catch(self, fallback: "Task") -> "Task":
        """Run *fallback* if this task fails."""

        async def _fallback(result: TaskResult) -> None:
            """Fallback

            Args:
                result: [description]

            Returns:
                [description]

            Raises:
                [description]
            """
            pass

        self.on_failure(_fallback)
        self.metadata["_fallback"] = fallback.serialize()
        return self

    # ── execution ──────────────────────────────────────────────────────────

    async def run(self, *, timeout: Optional[float] = None) -> Any:
        """Execute the wrapped callable with full lifecycle management.

        Raises
        ------
        TaskError
            If the task is not in PENDING or RETRYING state.
        TaskTimeout
            If *timeout* (or the instance-level timeout) elapses.
        TaskCancelled
            If the underlying asyncio task is cancelled.
        """
        if self.status not in (TaskStatus.PENDING, TaskStatus.RETRYING):
            raise TaskError(
                f"Cannot run task in state '{self.status.value}'",
                task_id=self.id,
                queue_name=self.queue_name,
            )

        # Fire before-hooks
        await self._fire_hooks("before")

        self.status = TaskStatus.RUNNING
        self.started_at = time.time()
        self.attempt += 1

        effective_timeout = timeout or self.timeout

        try:
            if effective_timeout:
                value = await asyncio.wait_for(
                    self.func(*self.args, **self.kwargs),
                    timeout=effective_timeout,
                )
            else:
                value = await self.func(*self.args, **self.kwargs)

            return self._complete_success(value)

        except asyncio.TimeoutError:
            return self._complete_failure(
                TaskTimeout(
                    f"Task '{self.name}' timed out after {effective_timeout:.0f}s",
                    task_id=self.id,
                    queue_name=self.queue_name,
                )
            )
        except asyncio.CancelledError:
            return self._complete_cancelled()
        except Exception as exc:
            return self._complete_failure(exc)
        finally:
            self._done.set()
            await self._fire_hooks("after")

    # ── lifecycle completion helpers ───────────────────────────────────────

    def _complete_success(self, value: Any) -> Any:
        """Complete Success

        Args:
            value: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.status = TaskStatus.COMPLETED
        self.completed_at = time.time()
        self.result = self._make_result(status=TaskStatus.COMPLETED, result=value)
        asyncio.create_task(self._fire_callbacks("success", self.result))
        return value

    def _complete_failure(self, exc: Exception) -> None:
        """Complete Failure

        Args:
            exc: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.status = (
            TaskStatus.FAILED
            if self.attempt >= self.max_attempts
            else TaskStatus.RETRYING
        )
        self.completed_at = time.time()
        self.result = self._make_result(
            status=self.status,
            error=f"{type(exc).__name__}: {exc}",
        )
        if self.status == TaskStatus.FAILED:
            asyncio.create_task(self._fire_callbacks("failure", self.result))
        if not isinstance(exc, (TaskTimeout,)):
            raise exc
        raise exc

    def _complete_cancelled(self) -> None:
        """Complete Cancelled

        Returns:
            [description]

        Raises:
            [description]
        """
        self.status = TaskStatus.CANCELLED
        self.completed_at = time.time()
        self.result = self._make_result(status=TaskStatus.CANCELLED)
        raise asyncio.CancelledError(f"Task '{self.name}' was cancelled") from None

    # ── result construction ────────────────────────────────────────────────

    def _make_result(
        self,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
    ) -> TaskResult:
        """Make Result

        Args:
            status: [description]
            result: [description]
            error: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return TaskResult(
            task_id=self.id,
            name=self.name,
            status=status,
            result=result,
            error=error,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            priority=self.priority,
            queue_name=self.queue_name,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            metadata=self.metadata,
        )

    # ── hook management ────────────────────────────────────────────────────

    async def _fire_hooks(self, group: str) -> None:
        """Fire Hooks

        Args:
            group: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        for hook in self._hooks[group]:
            try:
                await hook(self)
            except Exception:
                logger.warning(
                    f"{group}-hook for task '{self.name}' raised: {traceback.format_exc()}"
                )

    async def _fire_callbacks(self, group: str, result: TaskResult) -> None:
        """Fire Callbacks

        Args:
            group: [description]
            result: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        for cb in self._hooks[group]:
            try:
                await cb(result)
            except Exception:
                logger.warning(
                    f"{group}-callback for task '{self.name}' raised: {traceback.format_exc()}"
                )

    # ── waiting & cancellation ─────────────────────────────────────────────

    async def wait(self, timeout: Optional[float] = None) -> Any:
        """Wait

        Args:
            timeout: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.result is not None:
            return self._unwrap_result()
        await asyncio.wait_for(self._done.wait(), timeout=timeout)
        return self._unwrap_result()

    def _unwrap_result(self) -> Any:
        """Unwrap Result

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.result is None:
            return None
        if self.result.status == TaskStatus.FAILED and self.result.error:
            raise TaskError(
                self.result.error,
                task_id=self.id,
                queue_name=self.queue_name,
            )
        if self.result.status == TaskStatus.CANCELLED:
            raise TaskCancelled(
                f"Task '{self.name}' was cancelled",
                task_id=self.id,
                queue_name=self.queue_name,
            )
        return self.result.result

    def cancel(self) -> bool:
        """Cancel

        Returns:
            [description]

        Raises:
            [description]
        """
        if self._task and not self._task.done():
            return self._task.cancel()
        return False

    # ── serialisation ──────────────────────────────────────────────────────

    def serialize(self) -> str:
        """Serialize

        Returns:
            [description]

        Raises:
            [description]
        """
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "args": [str(a) for a in self.args],
                "kwargs": {k: str(v) for k, v in self.kwargs.items()},
                "priority": self.priority.value,
                "max_attempts": self.max_attempts,
                "queue_name": self.queue_name,
                "metadata": self.metadata,
                "timeout": self.timeout,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.name,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "queue": self.queue_name,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    # ── ordering (for heapq) ───────────────────────────────────────────────

    def __lt__(self, other: "Task") -> bool:
        """Lt

        Args:
            other: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return (-self.priority.value, self.created_at) < (
            -other.priority.value,
            other.created_at,
        )

    def __repr__(self) -> str:
        """Repr

        Returns:
            [description]

        Raises:
            [description]
        """
        return (
            f"Task(name={self.name!r}, status={self.status.value}, "
            f"pri={self.priority.name}, attempt={self.attempt}/{self.max_attempts})"
        )


# ────────────────────────────────────────────────────────────────── Decorator ──


def task(
    name: Optional[str] = None,
    *,
    priority: TaskPriority = TaskPriority.NORMAL,
    max_attempts: int = 1,
    queue: str = "default",
    timeout: Optional[float] = None,
) -> Callable:
    """Decorator that tags an async function as a task.

    Usage::

        @task(name="send-welcome", priority=TaskPriority.HIGH, max_attempts=3)
        async def send_welcome(email: str):
            ...

    The decorator attaches metadata attributes to the function object so
    that :meth:`Queue.put` can introspect them when no explicit arguments
    are supplied.
    """

    def decorator(func):
        """Decorator

        Args:
            func: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        func._work_task = True
        func._work_name = name or func.__name__
        func._work_priority = priority
        func._work_max_attempts = max_attempts
        func._work_queue = queue
        func._work_timeout = timeout
        func._work_func = func
        return func

    return decorator
