"""
sillo.work.scheduler — Timezone-aware cron, interval, and one-shot scheduling.

Supports three trigger types:
* ``IntervalTrigger(seconds)`` — every N seconds
* ``CronTrigger("min hour day month weekday")`` — standard cron syntax
* ``DateTrigger(at=timestamp)`` — fire once at a specific time

Jobs can be paused, resumed, removed, and inspected.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4

from .types import InvalidTrigger, JobStatus, SchedulerStats

logger = logging.getLogger("sillo.work.scheduler")


@dataclass
class IntervalTrigger:
    seconds: float
    jitter: float = 0.0

    def next_fire(self, last_fire: float) -> float:
        import random

        j = random.uniform(0, self.jitter) if self.jitter else 0
        return time.time() + self.seconds + j


@dataclass
class CronTrigger:
    expression: str
    timezone: Optional[str] = None

    def __post_init__(self):
        fields = self.expression.strip().split()
        if len(fields) != 5:
            raise InvalidTrigger("Cron requires 5 fields: min hour day month weekday")
        self._mins = self._parse(fields[0], 0, 59)
        self._hrs = self._parse(fields[1], 0, 23)
        self._days = self._parse(fields[2], 1, 31)
        self._mons = self._parse(fields[3], 1, 12)
        self._wdays = self._parse(fields[4], 0, 6)

    @staticmethod
    def _parse(field: str, lo: int, hi: int) -> set:
        if field == "*":
            return set(range(lo, hi + 1))
        result = set()
        for part in field.split(","):
            step = 1
            if "/" in part:
                part, s = part.split("/")
                step = int(s)
            if "-" in part:
                a, b = part.split("-")
                r = range(int(a), int(b) + 1, step)
            elif part == "*":
                r = range(lo, hi + 1, step)
            else:
                r = range(int(part), int(part) + 1, step)
            result.update(r)
        return result

    def next_fire(self, last_fire: float) -> float:
        from datetime import datetime, timedelta

        base = last_fire if last_fire > 0 else time.time()
        dt = datetime.fromtimestamp(base)
        for _ in range(366 * 24 * 60):
            dt += timedelta(minutes=1)
            if dt.minute not in self._mins:
                continue
            if dt.hour not in self._hrs:
                continue
            if dt.day not in self._days:
                continue
            if dt.month not in self._mons:
                continue
            if dt.weekday() not in self._wdays:
                continue
            return dt.timestamp()
        return time.time() + 366 * 86400


@dataclass
class DateTrigger:
    at: float

    def next_fire(self, last_fire: float) -> Optional[float]:
        return None if last_fire > 0 else self.at


class ScheduledJob:
    def __init__(
        self,
        func,
        trigger,
        *,
        name=None,
        args=(),
        kwargs=None,
        max_instances=1,
        id=None,
    ):
        self.id = id or str(uuid4())
        self.name = name or func.__name__
        self.func = func
        self.trigger = trigger
        self.args = args
        self.kwargs = kwargs or {}
        self.max_instances = max_instances
        self.status = JobStatus.ACTIVE
        self.next_run_time: Optional[float] = None
        self.last_run_time: float = 0
        self._runs = 0
        self._errors = 0
        self.current_instances = 0

    def compute_next(self, now=None):
        now = now or time.time()
        result = self.trigger.next_fire(self.last_run_time)
        if result is None:
            self.status = JobStatus.COMPLETED
            self.next_run_time = None
        else:
            self.next_run_time = result

    def pause(self):
        if self.status == JobStatus.ACTIVE:
            self.status = JobStatus.PAUSED

    def resume(self):
        if self.status == JobStatus.PAUSED:
            self.status = JobStatus.ACTIVE

    def cancel(self):
        self.status = JobStatus.CANCELLED

    async def run(self):
        self.last_run_time = time.time()
        self.current_instances += 1
        self._runs += 1
        try:
            return await self.func(*self.args, **self.kwargs)
        except Exception:
            self._errors += 1
            raise
        finally:
            self.current_instances -= 1
            if isinstance(self.trigger, DateTrigger):
                self.status = JobStatus.COMPLETED

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "runs": self._runs,
            "errors": self._errors,
            "next_run": self.next_run_time,
        }


class Scheduler:
    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._ticker: Optional[asyncio.Task] = None

    def schedule(self, func, trigger, *, name=None, **kwargs):
        job = ScheduledJob(func, trigger, name=name, **kwargs)
        job.compute_next()
        self._jobs[job.id] = job
        logger.info(f"Scheduled: {job.name} ({type(trigger).__name__})")
        return job

    def every(self, seconds, *, name=None):
        def d(f):
            return self.schedule(f, IntervalTrigger(seconds), name=name or f.__name__)

        return d

    def cron(self, expression, *, name=None):
        def d(f):
            return self.schedule(f, CronTrigger(expression), name=name or f.__name__)

        return d

    def remove(self, job_id):
        j = self._jobs.pop(job_id, None)
        if j:
            j.cancel()
        return j is not None

    def get(self, job_id):
        return self._jobs.get(job_id)

    def list(self, status=None):
        if status is None:
            return list(self._jobs.values())
        return [j for j in self._jobs.values() if j.status == status]

    def pause(self, job_id):
        j = self._jobs.get(job_id)
        if j:
            j.pause()
            return True
        return False

    def resume(self, job_id):
        j = self._jobs.get(job_id)
        if j:
            j.resume()
            j.compute_next()
            return True
        return False

    @property
    def stats(self) -> SchedulerStats:
        jobs = list(self._jobs.values())
        return SchedulerStats(
            jobs_total=len(jobs),
            jobs_active=sum(1 for j in jobs if j.status == JobStatus.ACTIVE),
            jobs_paused=sum(1 for j in jobs if j.status == JobStatus.PAUSED),
            runs_total=sum(j._runs for j in jobs),
            errors_total=sum(j._errors for j in jobs),
        )

    async def start(self):
        self._running = True
        self._ticker = asyncio.create_task(self._loop())
        logger.info(f"Scheduler ({len(self._jobs)} jobs)")

    async def stop(self):
        self._running = False
        if self._ticker:
            self._ticker.cancel()
            try:
                await self._ticker
            except asyncio.CancelledError:
                pass
        for j in self._jobs.values():
            j.cancel()
        logger.info("Scheduler stopped")

    async def _loop(self):
        while self._running:
            try:
                now = time.time()
                for job in list(self._jobs.values()):
                    if job.status != JobStatus.ACTIVE:
                        continue
                    if job.next_run_time and job.next_run_time <= now:
                        if job.current_instances >= job.max_instances:
                            continue
                        job.compute_next(now)
                        asyncio.create_task(self._execute(job))
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler loop")
                await asyncio.sleep(1)

    async def _execute(self, job):
        try:
            await job.run()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(f"Job {job.name} failed")
