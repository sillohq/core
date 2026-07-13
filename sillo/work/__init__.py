"""
sillo.work — Production-grade background tasks, queues, workers, and scheduling.

Central orchestration via :func:`setup_work` which configures a default
queue and scheduler into ``app.state["work"]`` for DI access.

Usage::

    from sillo.work import setup_work, Queue, Worker, BackgroundTask

    work = setup_work(app)
    queue = work["queue"]

    await queue.put(send_email, "user@ex.com")
    worker = Worker(queue, concurrency=4)
    await worker.start()
"""

from .background import BackgroundTask
from .backends import MemoryBackend, RedisBackend
from .middleware import LoggingMiddleware, RateLimitMiddleware, TimeoutMiddleware
from .queue import Queue
from .scheduler import Scheduler, CronTrigger, DateTrigger, IntervalTrigger, JobStatus, ScheduledJob
from .task import task
from .types import (
    CircuitBreakerOpen,
    CircuitState,
    QueueFull,
    QueueHealth,
    QueueStats,
    SchedulerStats,
    TaskCancelled,
    TaskError,
    TaskPriority,
    TaskRejected,
    TaskResult,
    TaskStatus,
    TaskTimeout,
    WorkerStats,
    WorkError,
)
from .worker import Worker

__all__ = [
    "Queue", "Worker", "Scheduler", "BackgroundTask",
    "TaskPriority", "TaskStatus", "TaskResult",
    "TaskError", "TaskTimeout", "TaskCancelled", "TaskRejected",
    "IntervalTrigger", "CronTrigger", "DateTrigger",
    "ScheduledJob", "JobStatus", "TriggerType",
    "MemoryBackend", "RedisBackend",
    "TimeoutMiddleware", "RateLimitMiddleware", "LoggingMiddleware",
    "CircuitBreakerOpen", "CircuitState", "WorkerStats",
    "QueueFull", "QueueHealth", "QueueStats", "SchedulerStats",
    "WorkError", "task",
]


def setup_work(app, *, queue_backend=None, queue_name: str = "default") -> dict:
    state = app.state
    if "work" in state:
        return state["work"]

    q = Queue(queue_name, backend=queue_backend or MemoryBackend())
    s = Scheduler()
    state["work"] = {"queue": q, "scheduler": s}

    app.on_startup(s.start)
    app.on_shutdown(s.stop)

    return state["work"]
