"""
sillo.work.types — Core type system for the work subsystem.

Defines every enum, dataclass, exception, and protocol used across the
entire work module.  All other modules import from here so types never
create circular dependencies.

Design principles
-----------------
* Exceptions carry structured context (task_id, queue_name, attempt).
* Enums use ``str`` values for JSON serialisation and log readability.
* Dataclasses are frozen where identity should be immutable after creation.
* TaskResult is the single source of truth for any completed unit of work.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import time
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple, Type, Union

# ───────────────────────────────────────────────────────────────────── Enum ─────


class TaskPriority(enum.IntEnum):
    """Ordered so that higher numerical values mean higher urgency.

    ``CRITICAL`` = 3  → dequeued first
    ``HIGH``    = 2
    ``NORMAL``  = 1
    ``LOW``     = 0  → dequeued last

    The queue / worker backends multiply by a large constant and negate
    the value to produce an ordered-set score in Redis; the in-memory
    backend uses :meth:`Task.__lt__` which respects the same ordering.
    """

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(enum.Enum):
    """Lifecycle of a single task."""

    PENDING = "pending"  # enqueued, not yet attempted
    SCHEDULED = "scheduled"  # registered with scheduler, awaiting trigger
    RUNNING = "running"  # currently executing
    COMPLETED = "completed"  # finished successfully
    FAILED = "failed"  # exhausted all retries or fatal error
    CANCELLED = "cancelled"  # explicitly cancelled before completion
    RETRYING = "retrying"  # between attempts, waiting for backoff


class TriggerType(enum.Enum):
    """Triggertype

    Returns:
        [description]

    Raises:
        [description]
    """

    INTERVAL = "interval"
    CRON = "cron"
    DATETIME = "datetime"


class JobStatus(enum.Enum):
    """Jobstatus

    Returns:
        [description]

    Raises:
        [description]
    """

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CircuitState(enum.Enum):
    """Circuitstate

    Returns:
        [description]

    Raises:
        [description]
    """

    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failures exceeded threshold
    HALF_OPEN = "half_open"  # testing recovery


class QueueHealth(enum.Enum):
    """Queuehealth

    Returns:
        [description]

    Raises:
        [description]
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # high backlog
    STALLED = "stalled"  # no consumers


# ──────────────────────────────────────────────────────────────── Exceptions ──


class WorkError(Exception):
    """Base for all work-related errors."""

    def __init__(self, message: str, *, task_id: str = "", queue_name: str = ""):
        """Init

        Args:
            message: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        super().__init__(message)
        self.task_id = task_id
        self.queue_name = queue_name


TaskError = WorkError  # alias for backward compat


class TaskRejected(WorkError):
    """Queue refused to accept the task (e.g. duplicate, full)."""


class TaskTimeout(WorkError):
    """Task did not complete within its configured time budget."""


class TaskCancelled(WorkError):
    """Task was cancelled externally."""


class QueueFull(WorkError):
    """Backend queue has reached capacity."""


class BackendUnavailable(WorkError):
    """Cannot reach the persistence backend."""


class CircuitBreakerOpen(WorkError):
    """Worker circuit is open — requests are being shed."""


class InvalidTrigger(WorkError):
    """Scheduler trigger configuration is malformed."""


# ──────────────────────────────────────────────────────────────── Dataclasses ─


@dataclasses.dataclass(frozen=True, slots=True)
class TaskResult:
    """Immutable snapshot of a finished (or failed) unit of work.

    Once populated, this object is the canonical record.  Backends may
    persist it; callbacks receive a reference to it.
    """

    task_id: str
    name: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 0
    priority: TaskPriority = TaskPriority.NORMAL
    queue_name: str = "default"
    created_at: float = dataclasses.field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    worker_id: str = ""

    # ── derived properties ──────────────────────────────────────────────

    @property
    def duration_ms(self) -> int:
        """Wall-clock execution time in milliseconds."""
        if not self.started_at or not self.completed_at:
            return 0
        return int((self.completed_at - self.started_at) * 1000)

    @property
    def latency_ms(self) -> int:
        """Time from creation to start in milliseconds."""
        if not self.created_at or not self.started_at:
            return 0
        return int((self.started_at - self.created_at) * 1000)

    @property
    def ok(self) -> bool:
        """Ok

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.status == TaskStatus.COMPLETED

    @property
    def is_terminal(self) -> bool:
        """Is Terminal

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

    # ── serialisation ───────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "result": self._serialise_result(),
            "error": self.error,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "priority": self.priority.name,
            "queue": self.queue_name,
            "duration_ms": self.duration_ms,
            "latency_ms": self.latency_ms,
            "worker": self.worker_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def to_json(self) -> str:
        """To Json

        Returns:
            [description]

        Raises:
            [description]
        """
        return json.dumps(self.to_dict(), default=str)

    def _serialise_result(self) -> Optional[str]:
        """Serialise Result

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.result is None:
            return None
        try:
            s = str(self.result)
            return s[:500] + "…" if len(s) > 500 else s
        except Exception:
            return "<unserialisable>"

    def __repr__(self) -> str:
        """Repr

        Returns:
            [description]

        Raises:
            [description]
        """
        return (
            f"TaskResult(id={self.task_id[:8]}, name={self.name!r}, "
            f"status={self.status.value}, attempt={self.attempt})"
        )


@dataclasses.dataclass
class QueueStats:
    """Current snapshot of a queue's state."""

    name: str
    size: int = 0
    completed: int = 0
    failed: int = 0
    oldest_age_ms: int = 0
    status: QueueHealth = QueueHealth.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "name": self.name,
            "size": self.size,
            "completed": self.completed,
            "failed": self.failed,
            "oldest_age_ms": self.oldest_age_ms,
            "status": self.status.value,
        }


@dataclasses.dataclass
class WorkerStats:
    """Current snapshot of a worker pool."""

    processed: int = 0
    failed: int = 0
    active: int = 0
    workers: int = 0
    circuit: CircuitState = CircuitState.CLOSED
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "processed": self.processed,
            "failed": self.failed,
            "active": self.active,
            "workers": self.workers,
            "circuit": self.circuit.value,
            "uptime": int(self.uptime_seconds),
        }


@dataclasses.dataclass
class SchedulerStats:
    """Schedulerstats

    Returns:
        [description]

    Raises:
        [description]
    """

    jobs_total: int = 0
    jobs_active: int = 0
    jobs_paused: int = 0
    runs_total: int = 0
    errors_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "jobs_total": self.jobs_total,
            "jobs_active": self.jobs_active,
            "jobs_paused": self.jobs_paused,
            "runs": self.runs_total,
            "errors": self.errors_total,
        }
