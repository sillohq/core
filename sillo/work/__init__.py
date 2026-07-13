"""sillo.work — Background tasks, advanced queue subsystem, and scheduling."""

from .backends import MemoryBackend, RedisBackend
from .middleware import LoggingMiddleware, RateLimitMiddleware, TimeoutMiddleware
from .task import task
from .types import (
    CircuitBreakerOpen, CircuitState, QueueFull, QueueHealth, QueueStats,
    SchedulerStats, TaskCancelled, TaskError, TaskPriority, TaskRejected,
    TaskResult, TaskStatus, TaskTimeout, WorkerStats, WorkError,
)

__all__ = [
    "TaskPriority", "TaskStatus", "TaskResult",
    "TaskError", "TaskTimeout", "TaskCancelled", "TaskRejected",
    "MemoryBackend", "RedisBackend",
    "TimeoutMiddleware", "RateLimitMiddleware", "LoggingMiddleware",
    "CircuitBreakerOpen", "CircuitState", "WorkerStats",
    "QueueFull", "QueueHealth", "QueueStats", "SchedulerStats", "WorkError",
    "task",
]


def setup_work(app, *, queue_backend=None, queue_name: str = "default") -> dict:
    """Wire up work subsystems into app.state."""
    state = app.state
    if "work" in state:
        return state["work"]
    from .queue import SyncConnection
    from .scheduler.manager import SchedulerManager
    conn = SyncConnection()
    s = SchedulerManager()
    state["work"] = {"connection": conn, "scheduler": s}
    app.on_startup(s.start)
    app.on_shutdown(s.stop)
    return state["work"]
