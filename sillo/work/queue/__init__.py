"""sillo.work.queue — Laravel-style queue subsystem."""

from .connection import (
    ConnectionManager,
    QueueConnection,
    SyncConnection,
    RedisConnection,
)
from .events import Event, EventDispatcher, listen
from .failed import FailedJob, FailedJobRepository, MemoryFailedRepository
from .job import Job, Dispatchable, dispatch
from .listener import EventListener, ListenerRegistry, WildcardListener
from .middleware import (
    JobMiddleware,
    RateLimitMiddleware as QRateLimitMiddleware,
    RetryMiddleware as QRetryMiddleware,
    TimeoutMiddleware as QTimeoutMiddleware,
)
from .payloads import JobPayload, PayloadSerializer
from .workers import QueueWorker, WorkerOptions, WorkerPool
from .batches import Batch, JobChain

__all__ = [
    "ConnectionManager",
    "QueueConnection",
    "SyncConnection",
    "RedisConnection",
    "Event",
    "EventDispatcher",
    "listen",
    "FailedJob",
    "FailedJobRepository",
    "MemoryFailedRepository",
    "Job",
    "Dispatchable",
    "dispatch",
    "EventListener",
    "ListenerRegistry",
    "WildcardListener",
    "JobMiddleware",
    "QRateLimitMiddleware",
    "QRetryMiddleware",
    "QTimeoutMiddleware",
    "JobPayload",
    "PayloadSerializer",
    "QueueWorker",
    "WorkerOptions",
    "WorkerPool",
    "Batch",
    "JobChain",
]
