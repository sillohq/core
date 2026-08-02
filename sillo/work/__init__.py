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
    WorkerStats,
    WorkError,
)

__all__ = [
    "TaskPriority",
    "TaskStatus",
    "TaskResult",
    "TaskError",
    "TaskTimeout",
    "TaskCancelled",
    "TaskRejected",
    "MemoryBackend",
    "RedisBackend",
    "TimeoutMiddleware",
    "RateLimitMiddleware",
    "LoggingMiddleware",
    "CircuitBreakerOpen",
    "CircuitState",
    "WorkerStats",
    "QueueFull",
    "QueueHealth",
    "QueueStats",
    "SchedulerStats",
    "WorkError",
    "task",
]


def setup_work(app, *, queue_backend=None, queue_name: str = "default") -> dict:
    """Wire up work subsystems into app.state and register DI providers."""
    state = app.state
    if "work" in state:
        return state["work"]
    from .queue import SyncConnection
    from .scheduler.manager import SchedulerManager
    from .queue.events import EventDispatcher

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
# tooling to call. sillo ships no CLI; sillo-start and your scripts consume
# these.
from sillo.work import commands  # noqa: E402,F401
