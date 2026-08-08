"""sillo.work.queue — Laravel-style queue subsystem."""

from .batches import Batch, JobChain
from .connection import (
    ConnectionManager,
    QueueConnection,
    RedisConnection,
    SyncConnection,
)
from .events import Event, EventDispatcher, listen
from .failed import FailedJob, FailedJobRepository, MemoryFailedRepository
from .job import Dispatchable, Job, dispatch
from .listener import EventListener, ListenerRegistry, WildcardListener
from .middleware import (
    JobMiddleware,
)
from .middleware import (
    RateLimitMiddleware as QRateLimitMiddleware,
)
from .middleware import (
    RetryMiddleware as QRetryMiddleware,
)
from .middleware import (
    TimeoutMiddleware as QTimeoutMiddleware,
)
from .payloads import JobPayload, PayloadSerializer
from .workers import QueueWorker, WorkerOptions, WorkerPool

__all__ = [
    "Batch",
    "ConnectionManager",
    "Dispatchable",
    "Event",
    "EventDispatcher",
    "EventListener",
    "FailedJob",
    "FailedJobRepository",
    "Job",
    "JobChain",
    "JobMiddleware",
    "JobPayload",
    "ListenerRegistry",
    "MemoryFailedRepository",
    "PayloadSerializer",
    "QRateLimitMiddleware",
    "QRetryMiddleware",
    "QTimeoutMiddleware",
    "QueueConnection",
    "QueueWorker",
    "RedisConnection",
    "SyncConnection",
    "WildcardListener",
    "WorkerOptions",
    "WorkerPool",
    "dispatch",
    "listen",
]
