"""
sillo.work.middleware — Task middleware hooks.

Middleware wraps task execution with cross-cutting concerns.

Built-in:
* TimeoutMiddleware — enforce per-task execution deadline
* RateLimitMiddleware — throttle task execution rate (token bucket)
* LoggingMiddleware — structured logging of task lifecycle
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .task import Task
from .types import TaskResult

logger = logging.getLogger("sillo.work.middleware")


class TimeoutMiddleware:
    """Timeoutmiddleware

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, timeout: float):
        """Init

        Args:
            timeout: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.timeout = timeout

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def before_execute(self, task: Task) -> None:
        """Before Execute

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if not getattr(task, "timeout", None):
            object.__setattr__(task, "timeout", self.timeout)

    async def after_execute(self, result: TaskResult) -> None:
        """After Execute

        Args:
            result: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error

        Args:
            task: [description]
            error: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass


class RateLimitMiddleware:
    """Ratelimitmiddleware

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, max_per_second: float, burst: int = 1):
        """Init

        Args:
            max_per_second: [description]
            burst: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.max_per_second = max_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def before_execute(self, task: Task) -> None:
        """Before Execute

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self.burst), self._tokens + elapsed * self.max_per_second
        )
        self._last_refill = now
        if self._tokens < 1:
            wait = (1 - self._tokens) / self.max_per_second
            await asyncio.sleep(wait)
            self._tokens = 0
            self._last_refill = time.monotonic()
        else:
            self._tokens -= 1

    async def after_execute(self, result: TaskResult) -> None:
        """After Execute

        Args:
            result: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error

        Args:
            task: [description]
            error: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass


class LoggingMiddleware:
    """Loggingmiddleware

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, level: int = logging.DEBUG):
        """Init

        Args:
            level: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.level = level

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        logger.log(self.level, f"ENQUEUE {task.name} [{task.id[:8]}]")

    async def before_execute(self, task: Task) -> None:
        """Before Execute

        Args:
            task: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        logger.log(self.level, f"START   {task.name} [{task.id[:8]}]")

    async def after_execute(self, result: TaskResult) -> None:
        """After Execute

        Args:
            result: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        logger.log(
            self.level,
            f"DONE    {result.name} [{result.task_id[:8]}] ok={result.ok} ({result.duration_ms}ms)",
        )

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error

        Args:
            task: [description]
            error: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        logger.log(
            logging.WARNING,
            f"ERROR   {task.name} [{task.id[:8]}] {type(error).__name__}",
        )
