"""
sillo.work.scheduler — Advanced cron and interval scheduler for sillo.

Features:
- Cron, interval, date, and compound triggers
- Per-job middleware (timeout, rate-limit, retry)
- DI integration via app.state["scheduler"]
- Stats and monitoring
"""

from .manager import SchedulerManager, SchedulerStats, setup_scheduler
from .triggers import (
    CompoundLogic,
    CompoundTrigger,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
    TriggerType,
)
from .jobs import ScheduledJob, JobStatus

__all__ = [
    "SchedulerManager", "SchedulerStats", "setup_scheduler",
    "CronTrigger", "IntervalTrigger", "DateTrigger", "CompoundTrigger",
    "CompoundLogic", "TriggerType", "ScheduledJob", "JobStatus",
]
