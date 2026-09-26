"""sillo.work — Background tasks, advanced queue subsystem, and scheduling."""

from .backends import MemoryBackend, RedisBackend
from .middleware import LoggingMiddleware, RateLimitMiddleware, TimeoutMiddleware
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
    WorkError,
    WorkerStats,
)

__all__ = [
    "CircuitBreakerOpen",
    "CircuitState",
    "LoggingMiddleware",
    "MemoryBackend",
    "QueueFull",
    "QueueHealth",
    "QueueStats",
    "RateLimitMiddleware",
    "RedisBackend",
    "SchedulerStats",
    "TaskCancelled",
    "TaskError",
    "TaskPriority",
    "TaskRejected",
    "TaskResult",
    "TaskStatus",
    "TaskTimeout",
    "TimeoutMiddleware",
    "Work",
    "WorkError",
    "WorkerStats",
    "task",
]


class Work:
    """Install queue work and its scheduler as one application subsystem."""

    name = "work"

    def __init__(self, *, queue_backend=None, queue_name: str = "default") -> None:
        self.queue_backend = queue_backend
        self.queue_name = queue_name

    def install(self, app) -> dict:
        from .queue import SyncConnection
        from .queue.events import EventDispatcher
        from .scheduler.manager import SchedulerManager

        conn = SyncConnection()
        scheduler = SchedulerManager()
        dispatcher = EventDispatcher()
        # Keep every established state key: jobs and scheduler consumers use
        # them independently even though Work owns their shared setup.
        app.state["work"] = {"connection": conn, "scheduler": scheduler}
        app.state["scheduler"] = scheduler
        app.state["queue_connection"] = conn
        app.state["events"] = dispatcher
        app.on_startup(scheduler.start)
        app.on_shutdown(scheduler.stop)
        return app.state["work"]


def setup_work(app, *, queue_backend=None, queue_name: str = "default") -> dict:
    """Install :class:`Work`; kept as the compatible functional API."""

    return app.install(Work(queue_backend=queue_backend, queue_name=queue_name))


# Queue and scheduler operations as plain functions, for a project's own
# tooling to call. The `sillo` command, sillo-start and your scripts consume
# these.
from sillo.work import commands
