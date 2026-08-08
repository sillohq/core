"""
sillo.work.scheduler — Advanced cron and interval scheduler for sillo.

Features:
- Cron, interval, date, and compound triggers
- Per-job middleware (timeout, rate-limit, retry)
- DI integration via app.state["scheduler"]
- Stats and monitoring
"""

from .jobs import JobStatus, ScheduledJob
from .manager import SchedulerManager, SchedulerStats, setup_scheduler
from .triggers import (
    CompoundLogic,
    CompoundTrigger,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
    TriggerType,
)

__all__ = [
    "CompoundLogic",
    "CompoundTrigger",
    "CronTrigger",
    "DateTrigger",
    "IntervalTrigger",
    "JobStatus",
    "ScheduledJob",
    "SchedulerManager",
    "SchedulerStats",
    "TriggerType",
    "setup_scheduler",
]
