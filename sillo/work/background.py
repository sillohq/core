"""
sillo.work.background — Fire-and-forget background tasks.

``BackgroundTask`` runs a coroutine in the background and provides
a handle to wait, cancel, or inspect the result.

Tasks are tracked in a class-level set for drain operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from .task import Task
from .types import TaskResult

logger = logging.getLogger("sillo.work.background")


class BackgroundTask:
    _instances: set = set()

    def __init__(self, func: Callable[..., Awaitable[Any]], *args: Any, name: Optional[str] = None, on_done: Optional[Callable[[TaskResult], Awaitable[None]]] = None, **kwargs: Any):
        self._task_obj = Task(func, *args, name=name or func.__name__, **kwargs)
        if on_done:
            self._task_obj.on_success(on_done).on_failure(on_done)
        self._asyncio_task = asyncio.ensure_future(self._task_obj.run())
        BackgroundTask._instances.add(self)

    async def wait(self, timeout: Optional[float] = None) -> Any:
        return await self._task_obj.wait(timeout=timeout)

    def cancel(self) -> bool:
        if self._asyncio_task and not self._asyncio_task.done():
            return self._asyncio_task.cancel()
        return False

    @property
    def done(self) -> bool:
        return self._task_obj.is_done

    @property
    def result(self) -> Optional[TaskResult]:
        return self._task_obj.result

    @classmethod
    def run(cls, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> "BackgroundTask":
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError("BackgroundTask.run() requires an async context")
        return cls(func, *args, **kwargs)

    @classmethod
    async def drain(cls, timeout: float = 10.0) -> None:
        instances = list(cls._instances)
        if instances:
            tasks = [i._asyncio_task for i in instances]
            await asyncio.wait(tasks, timeout=timeout)
            for t in tasks:
                if not t.done():
                    t.cancel()
