"""
sillo.work.scheduler.manager — Scheduler manager with persistence and DI support.

The ``SchedulerManager`` coordinates all registered scheduled jobs, runs
a ticker loop, and integrates with the sillo application lifecycle via
``app.state`` and startup/shutdown hooks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional

from typing_extensions import Doc

from .jobs import ScheduledJob, JobStatus
from .triggers import CronTrigger, DateTrigger, IntervalTrigger

logger = logging.getLogger("sillo.work.scheduler.manager")


class SchedulerStats:
    """Aggregated statistics for a scheduler instance."""

    def __init__(self):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        self.jobs_total = 0
        self.jobs_active = 0
        self.jobs_paused = 0
        self.runs_total = 0
        self.errors_total = 0
        self.uptime_seconds = 0.0

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
        sched = request.app.state["scheduler"]
        sched.pause("job-id")
    """

    def __init__(self):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._ticker: Optional[asyncio.Task] = None
        self._started_at: float = 0.0

    # ── registration ─────────────────────────────────────────────────────

    def schedule(
        self,
        func: Annotated[Callable[..., Awaitable[Any]], Doc("Async callable.")],
        trigger: Annotated[Any, Doc("Trigger instance.")],
        *,
        name: Annotated[Optional[str], Doc("Label.")] = None,
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
        name: Annotated[Optional[str], Doc("Label.")] = None,
    ) -> Callable:
        """Decorator: run every *seconds*."""

        def decorator(func):
            """Decorator

                Args:
                    func: [description]

                Returns:
                    [description]

                Raises:
                    [description]
            """
            return self.schedule(
                func, IntervalTrigger(seconds), name=name or func.__name__
            )

        return decorator

    def cron(
        self,
        expression: Annotated[str, Doc("Cron expression.")],
        *,
        name: Annotated[Optional[str], Doc("Label.")] = None,
    ) -> Callable:
        """Decorator: run on a cron schedule."""

        def decorator(func):
            """Decorator

                Args:
                    func: [description]

                Returns:
                    [description]

                Raises:
                    [description]
            """
            return self.schedule(
                func, CronTrigger(expression), name=name or func.__name__
            )

        return decorator

    # ── job management ────────────────────────────────────────────────────

    def remove(self, job_id: Annotated[str, Doc("Job ID.")]) -> bool:
        """Remove a job. Returns True if found."""
        j = self._jobs.pop(job_id, None)
        if j:
            j.cancel()
        return j is not None

    def get(self, job_id: Annotated[str, Doc("Job ID.")]) -> Optional[ScheduledJob]:
        """Look up a job by ID."""
        return self._jobs.get(job_id)

    def list(self, status: Optional[JobStatus] = None) -> List[ScheduledJob]:
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
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Loop

            Returns:
                [description]

            Raises:
                [description]
        """
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
                        asyncio.create_task(self._execute(job))
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler loop")
                await asyncio.sleep(1)

    async def _execute(self, job: ScheduledJob) -> None:
        """Execute

            Args:
                job: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        try:
            await job.run()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Job %s failed", job.name)


def setup_scheduler(app) -> SchedulerManager:
    """Wire a SchedulerManager into the app lifecycle.

    Stores in ``app.state["scheduler"]``.  Call ``scheduler.start()``
    manually or use the auto-start feature.

    Usage::

        app = silloApp()
        scheduler = setup_scheduler(app)
        scheduler.every(3600)(my_cleanup_task)
    """
    if "scheduler" in app.state:
        return app.state["scheduler"]
    s = SchedulerManager()
    app.state["scheduler"] = s
    app.on_startup(s.start)
    app.on_shutdown(s.stop)
    return s
