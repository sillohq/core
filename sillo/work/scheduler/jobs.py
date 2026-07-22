"""
sillo.work.scheduler.jobs — Scheduled job with middleware, retry, and DI support.

A ``ScheduledJob`` wraps a callable with a trigger, tracks execution
history, and supports per-job middleware for rate limiting, timeout,
and retry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4

from typing_extensions import Doc

from .triggers import DateTrigger

logger = logging.getLogger("sillo.work.scheduler.jobs")


class JobStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScheduledJob:
    """A callable bound to a trigger with execution tracking.

    Parameters
    ----------
    func:
        Async callable to execute.
    trigger:
        One of ``IntervalTrigger``, ``CronTrigger``, ``DateTrigger``,
        or ``CompoundTrigger``.
    name:
        Human-readable label (defaults to ``func.__name__``).
    args, kwargs:
        Positional and keyword arguments forwarded to *func*.
    max_instances:
        Maximum concurrent executions. 0 = unlimited.
    coalesce:
        If True, skip a run if the previous one is still executing.
    middleware:
        List of callable middleware factories.
    """

    def __init__(
        self,
        func: Annotated[
            Callable[..., Awaitable[Any]], Doc("Async callable to schedule.")
        ],
        trigger: Annotated[Any, Doc("Trigger instance.")],
        *,
        name: Annotated[Optional[str], Doc("Human-readable label.")] = None,
        args: Annotated[tuple, Doc("Positional arguments for func.")] = (),
        kwargs: Annotated[
            Optional[Dict[str, Any]], Doc("Keyword arguments for func.")
        ] = None,
        max_instances: Annotated[int, Doc("Max concurrent runs. 0 = unlimited.")] = 1,
        coalesce: Annotated[bool, Doc("Skip if previous run still active.")] = True,
        middleware: Annotated[Optional[List[Any]], Doc("Middleware factories.")] = None,
        id: Annotated[
            Optional[str], Doc("Explicit job ID. Auto-generated if omitted.")
        ] = None,
    ):
        self.id = id or str(uuid4())
        self.name = name or func.__name__
        self.func = func
        self.trigger = trigger
        self.args = args
        self.kwargs = kwargs or {}
        self.max_instances = max_instances
        self.coalesce = coalesce
        self._middleware_factories = middleware or []
        self.status = JobStatus.ACTIVE
        self.next_run_time: Optional[float] = None
        self.last_run_time: float = 0
        self._runs = 0
        self._errors = 0
        self.current_instances = 0
        self.created_at = time.time()

    def compute_next(self, now: Optional[float] = None) -> None:
        """Calculate and store the next fire timestamp."""
        result = self.trigger.next_fire(self.last_run_time)
        if result is None:
            self.status = JobStatus.COMPLETED
            self.next_run_time = None
        else:
            self.next_run_time = result

    def pause(self) -> None:
        """Pause scheduling. The job will not fire until resumed."""
        if self.status == JobStatus.ACTIVE:
            self.status = JobStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused job."""
        if self.status == JobStatus.PAUSED:
            self.status = JobStatus.ACTIVE

    def cancel(self) -> None:
        """Permanently cancel this job."""
        self.status = JobStatus.CANCELLED

    async def run(self) -> Any:
        """Execute the callable through the middleware pipeline."""
        self.last_run_time = time.time()
        self.current_instances += 1
        self._runs += 1

        handler = self.func
        for mw_factory in reversed(self._middleware_factories):
            handler = await mw_factory(handler, self)

        try:
            result = await handler(*self.args, **self.kwargs)
            return result
        except Exception:
            self._errors += 1
            raise
        finally:
            self.current_instances -= 1

            if isinstance(self.trigger, DateTrigger):
                self.status = JobStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """Serialise job metadata for monitoring."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "runs": self._runs,
            "errors": self._errors,
            "next_run": self.next_run_time,
            "active_instances": self.current_instances,
            "created_at": self.created_at,
        }
