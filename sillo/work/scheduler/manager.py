"""
sillo.work.scheduler.manager — Scheduler manager with persistence and DI support.

The ``SchedulerManager`` coordinates all registered scheduled jobs, runs
a ticker loop, and integrates with the sillo application lifecycle via
``app.state`` and startup/shutdown hooks.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from typing_extensions import Doc

from sillo.cache import MISSING, BaseCache, RedisCache, get_default_backend

from .jobs import JobStatus, ScheduledJob
from .triggers import CronTrigger, IntervalTrigger

logger = logging.getLogger("sillo.work.scheduler.manager")


class SchedulerStats:
    """Aggregated statistics for a scheduler instance."""

    def __init__(self):
        """Init"""
        self.jobs_total = 0
        self.jobs_active = 0
        self.jobs_paused = 0
        self.runs_total = 0
        self.errors_total = 0
        self.uptime_seconds = 0.0

    def to_dict(self) -> dict[str, Any]:
        """To Dict"""
        return {
            "jobs_total": self.jobs_total,
            "jobs_active": self.jobs_active,
            "jobs_paused": self.jobs_paused,
            "runs": self.runs_total,
            "errors": self.errors_total,
            "uptime": int(self.uptime_seconds),
        }


class SchedulerManager:
    """Coordinates scheduled jobs with a ticker loop.

    Integrates with the sillo app lifecycle via ``app.state["scheduler"]``.

    Usage::

        scheduler = SchedulerManager()
        scheduler.schedule(my_job, CronTrigger("0 9 * * *"))
        scheduler.every(3600)(hourly_cleanup)

        # In a handler (via DI):
        sched = ctx.app.state["scheduler"]
        sched.pause("job-id")
    """

    def __init__(
        self,
        *,
        cache: BaseCache | None = None,
        lease: float = 60,
        namespace: str = "scheduler",
        claim_ttl: int = 604800,
    ):
        """Coordinate through an explicit cache or the configured Redis cache.

        Without Redis, the default remains an independent local scheduler.
        ``claim_ttl`` retains consumed occurrences beyond their next fire time.
        """
        if not math.isfinite(lease) or lease <= 0:
            raise ValueError("lease must be finite and greater than zero")
        if not namespace:
            raise ValueError("namespace must not be empty")
        if claim_ttl <= 0:
            raise ValueError("claim_ttl must be greater than zero")
        self.cache = cache
        self.lease = lease
        self.namespace = namespace
        self.claim_ttl = claim_ttl
        self._jobs: dict[str, ScheduledJob] = {}
        self._tasks: set[asyncio.Task] = set()
        self._running = False
        self._ticker: asyncio.Task | None = None
        self._started_at: float = 0.0

    # ── registration ─────────────────────────────────────────────────────

    def schedule(
        self,
        func: Annotated[Callable[..., Awaitable[Any]], Doc("Async callable.")],
        trigger: Annotated[Any, Doc("Trigger instance.")],
        *,
        name: Annotated[str | None, Doc("Label.")] = None,
        **kwargs,
    ) -> ScheduledJob:
        """Register a new scheduled job and return it."""
        job = ScheduledJob(func, trigger, name=name, **kwargs)
        job.compute_next()
        self._jobs[job.id] = job
        logger.info("Scheduled: %s (%s)", job.name, type(trigger).__name__)
        return job

    def every(
        self,
        seconds: Annotated[float, Doc("Interval in seconds.")],
        *,
        name: Annotated[str | None, Doc("Label.")] = None,
    ) -> Callable:
        """Decorator: run every *seconds*."""

        def decorator(func):
            """Decorator"""
            return self.schedule(func, IntervalTrigger(seconds), name=name)

        return decorator

    def cron(
        self,
        expression: Annotated[str, Doc("Cron expression.")],
        *,
        name: Annotated[str | None, Doc("Label.")] = None,
    ) -> Callable:
        """Decorator: run on a cron schedule."""

        def decorator(func):
            """Decorator"""
            return self.schedule(func, CronTrigger(expression), name=name)

        return decorator

    # ── job management ────────────────────────────────────────────────────

    def remove(self, job_id: Annotated[str, Doc("Job ID.")]) -> bool:
        """Remove a job. Returns True if found."""
        j = self._jobs.pop(job_id, None)
        if j:
            j.cancel()
        return j is not None

    def get(self, job_id: Annotated[str, Doc("Job ID.")]) -> ScheduledJob | None:
        """Look up a job by ID."""
        return self._jobs.get(job_id)

    def list(self, status: JobStatus | None = None) -> builtins.list[ScheduledJob]:
        """List all jobs, optionally filtered by status."""
        if status is None:
            return list(self._jobs.values())
        return [j for j in self._jobs.values() if j.status == status]

    def pause(self, job_id: Annotated[str, Doc("Job ID.")]) -> bool:
        """Pause a job. Returns True if found."""
        j = self._jobs.get(job_id)
        if j:
            j.pause()
            return True
        return False

    def resume(self, job_id: Annotated[str, Doc("Job ID.")]) -> bool:
        """Resume a paused job. Returns True if found."""
        j = self._jobs.get(job_id)
        if j:
            j.resume()
            j.compute_next()
            return True
        return False

    # ── stats ─────────────────────────────────────────────────────────────

    @property
    def stats(self) -> SchedulerStats:
        """Aggregated statistics."""
        s = SchedulerStats()
        s.uptime_seconds = time.time() - self._started_at if self._started_at else 0
        for j in self._jobs.values():
            s.jobs_total += 1
            if j.status == JobStatus.ACTIVE:
                s.jobs_active += 1
            if j.status == JobStatus.PAUSED:
                s.jobs_paused += 1
            s.runs_total += j._runs
            s.errors_total += j._errors
        return s

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Begin the ticker loop."""
        if self.cache is None:
            backend = get_default_backend()
            if isinstance(backend, RedisCache):
                self.cache = backend
        self._running = True
        self._started_at = time.time()
        self._ticker = asyncio.create_task(self._loop())
        logger.info("Scheduler started (%d jobs)", len(self._jobs))

    async def stop(self) -> None:
        """Gracefully stop the scheduler."""
        self._running = False
        if self._ticker:
            self._ticker.cancel()
            try:
                await self._ticker
            except asyncio.CancelledError:
                pass
        for j in self._jobs.values():
            j.cancel()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Loop"""
        while self._running:
            try:
                now = time.time()
                for job in list(self._jobs.values()):
                    if job.status != JobStatus.ACTIVE:
                        continue
                    if job.next_run_time and job.next_run_time <= now:
                        if (
                            job.max_instances
                            and job.current_instances >= job.max_instances
                        ):
                            continue
                        if job.coalesce and job.current_instances > 0:
                            continue
                        job.compute_next(now)
                        task = asyncio.create_task(self._execute(job))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler loop")
                await asyncio.sleep(1)

    async def _execute(self, job: ScheduledJob) -> None:
        """Execute"""
        try:
            if self.cache is None:
                await job.run()
            else:
                await self._execute_shared(job)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Job %s failed", job.name)

    async def _execute_shared(self, job: ScheduledJob) -> None:
        """Claim a fire under a renewable, non-blocking per-job lease."""
        cache = self.cache
        assert cache is not None
        key = cache.make_key(self.namespace, job.coordination_id)
        lock = cache.lock(key, lease=self.lease)
        if not await lock.acquire():
            # Advance even on contention: this worker must leave this fire alone.
            job.compute_next(time.time())
            return
        owner = asyncio.current_task()
        assert owner is not None
        renewal = asyncio.create_task(self._renew(lock, owner))
        try:
            now = time.time()
            next_fire = await cache.get(key)
            if next_fire is not MISSING and (next_fire is None or next_fire > now):
                job.next_run_time = next_fire
                if next_fire is None:
                    job.status = JobStatus.COMPLETED
                return
            job.compute_next(now)
            # Persist before executing. A late worker must not repeat a fast job
            # merely because its execution lease has already been released.
            ttl = max(
                self.claim_ttl,
                math.ceil((job.next_run_time or now) - now) + self.claim_ttl,
            )
            await cache.set(key, job.next_run_time, ttl=ttl)
            await job.run()
        finally:
            renewal.cancel()
            await asyncio.gather(renewal, return_exceptions=True)
            await lock.release()

    async def _renew(self, lock, owner: asyncio.Task) -> None:
        """Cancel execution if renewing ownership fails or Redis is unavailable."""
        try:
            while True:
                await asyncio.sleep(self.lease / 3)
                if not await lock.extend():
                    logger.error("Scheduler lease lost: %s", lock.name)
                    owner.cancel()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler lease renewal failed: %s", lock.name)
            owner.cancel()


class Scheduler:
    """Install a scheduler when an application does not already have one."""

    name = "scheduler"

    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs

    def install(self, app) -> SchedulerManager:
        # Work installs a scheduler as part of its larger subsystem.  Reuse it
        # rather than creating a second ticker when a project later asks for a
        # standalone Scheduler installable as well.
        if "scheduler" in app.state:
            return app.state["scheduler"]

        scheduler = SchedulerManager(**self._kwargs)
        app.state["scheduler"] = scheduler
        app.on_startup(scheduler.start)
        app.on_shutdown(scheduler.stop)
        return scheduler


def setup_scheduler(app, **kwargs) -> SchedulerManager:
    """Install :class:`Scheduler`; kept as the compatible functional API.

    Stores in ``app.state["scheduler"]``.  Call ``scheduler.start()``
    manually or use the auto-start feature.

    Usage::

        app = SilloApp()
        scheduler = setup_scheduler(app)
        scheduler.every(3600)(my_cleanup_task)
    """
    return app.install(Scheduler(**kwargs))
