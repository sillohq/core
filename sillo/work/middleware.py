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

from .task import Task
from .types import TaskResult

logger = logging.getLogger("sillo.work.middleware")


class TimeoutMiddleware:
    """Timeoutmiddleware"""

    def __init__(self, timeout: float):
        """Init"""
        self.timeout = timeout

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue"""

    async def before_execute(self, task: Task) -> None:
        """Before Execute"""
        if not getattr(task, "timeout", None):
            object.__setattr__(task, "timeout", self.timeout)

    async def after_execute(self, result: TaskResult) -> None:
        """After Execute"""

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error"""


class RateLimitMiddleware:
    """Ratelimitmiddleware"""

    def __init__(self, max_per_second: float, burst: int = 1):
        """Init"""
        self.max_per_second = max_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue"""

    async def before_execute(self, task: Task) -> None:
        """Before Execute"""
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
        """After Execute"""

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error"""


class LoggingMiddleware:
    """Loggingmiddleware"""

    def __init__(self, level: int = logging.DEBUG):
        """Init"""
        self.level = level

    async def before_enqueue(self, task: Task) -> None:
        """Before Enqueue"""
        logger.log(self.level, f"ENQUEUE {task.name} [{task.id[:8]}]")

    async def before_execute(self, task: Task) -> None:
        """Before Execute"""
        logger.log(self.level, f"START   {task.name} [{task.id[:8]}]")

    async def after_execute(self, result: TaskResult) -> None:
        """After Execute"""
        logger.log(
            self.level,
            f"DONE    {result.name} [{result.task_id[:8]}] ok={result.ok} ({result.duration_ms}ms)",
        )

    async def on_error(self, task: Task, error: Exception) -> None:
        """On Error"""
        logger.log(
            logging.WARNING,
            f"ERROR   {task.name} [{task.id[:8]}] {type(error).__name__}",
        )
