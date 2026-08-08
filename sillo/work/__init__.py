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
    "WorkError",
    "WorkerStats",
    "task",
]


def setup_work(app, *, queue_backend=None, queue_name: str = "default") -> dict:
    """Wire up work subsystems into app.state and register DI providers."""
    state = app.state
    if "work" in state:
        return state["work"]
    from .queue import SyncConnection
    from .queue.events import EventDispatcher
    from .scheduler.manager import SchedulerManager

    conn = SyncConnection()
    s = SchedulerManager()
    dispatcher = EventDispatcher()
    state["work"] = {"connection": conn, "scheduler": s}
    state["scheduler"] = s
    state["queue_connection"] = conn
    state["events"] = dispatcher
    app.on_startup(s.start)
    app.on_shutdown(s.stop)
    return state["work"]


# Queue and scheduler operations as plain functions, for a project's own
# tooling to call. The `sillo` command, sillo-start and your scripts consume
# these.
from sillo.work import commands
