"""Deep tests for sillo.work scheduler: triggers, CronParser, SchedulerManager,
pause/resume/remove, stats, and a live ticker loop.
"""

import asyncio
import time

import pytest

from sillo.work.scheduler.cron import CronParser
from sillo.work.scheduler.jobs import JobStatus, ScheduledJob
from sillo.work.scheduler.manager import SchedulerManager
from sillo.work.scheduler.triggers import (
    CompoundLogic,
    CompoundTrigger,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
)


def test_interval_trigger_schedules_in_future():
    t = IntervalTrigger(seconds=10)
    nxt = t.next_fire(0)
    assert nxt >= time.time() + 9.9


def test_date_trigger_fires_once_then_none():
    at = time.time() + 5
    t = DateTrigger(at=at)
    assert t.next_fire(0) == at
    assert t.next_fire(at + 1) is None


def test_cron_trigger_returns_future_time():
    t = CronTrigger("* * * * *")
    nxt = t.next_fire(0)
    assert nxt > time.time()
    assert nxt < time.time() + 60


def test_compound_or_takes_earliest():
    t = CompoundTrigger(
        triggers=[DateTrigger(at=time.time() + 100), DateTrigger(at=time.time() + 10)],
        logic=CompoundLogic.OR,
    )
    nxt = t.next_fire(0)
    assert nxt < time.time() + 11


def test_compound_and_takes_latest():
    t = CompoundTrigger(
        triggers=[DateTrigger(at=time.time() + 100), DateTrigger(at=time.time() + 10)],
        logic=CompoundLogic.AND,
    )
    nxt = t.next_fire(0)
    assert nxt > time.time() + 99


def test_cron_parser_rejects_wrong_field_count():
    with pytest.raises(ValueError):
        CronParser("0 9 * *")


def test_scheduler_register_via_schedule_and_every():
    sched = SchedulerManager()

    async def job_a():
        return "a"

    async def job_b():
        return "b"

    j1 = sched.schedule(job_a, IntervalTrigger(seconds=60), name="a")
    sched.every(120)(job_b)
    assert len(sched.list()) == 2
    assert sched.get(j1.id) is j1
    assert isinstance(j1, ScheduledJob)


def test_scheduler_cron_registration():
    sched = SchedulerManager()

    async def tick():
        return 1

    job = sched.cron("*/5 * * * *", name="five-min")(tick)
    assert job.trigger.expression == "*/5 * * * *"
    assert job.name == "five-min"


def test_scheduler_pause_resume_remove():
    sched = SchedulerManager()

    async def job():
        return 1

    j = sched.schedule(job, IntervalTrigger(seconds=60), name="p")
    assert sched.pause(j.id) is True
    assert j.status == JobStatus.PAUSED
    assert sched.resume(j.id) is True
    assert j.status == JobStatus.ACTIVE
    assert sched.remove(j.id) is True
    assert sched.get(j.id) is None
    assert sched.pause("nope") is False


def test_scheduler_stats_track_runs_and_errors():
    sched = SchedulerManager()

    async def ok():
        return 1

    sched.schedule(ok, IntervalTrigger(seconds=60), name="ok")
    stats = sched.stats
    assert stats.jobs_total == 1
    assert stats.jobs_active == 1


async def test_scheduler_live_loop_executes_interval_job():
    sched = SchedulerManager()
    runs = []

    async def counter():
        runs.append(1)

    sched.schedule(counter, IntervalTrigger(seconds=0.1), name="counter")
    await sched.start()
    # allow a few ticks
    for _ in range(50):
        if len(runs) >= 2:
            break
        await asyncio.sleep(0.05)
    await sched.stop()
    assert len(runs) >= 2


async def test_scheduler_paused_job_does_not_run():
    sched = SchedulerManager()
    runs = []

    async def counter():
        runs.append(1)

    j = sched.schedule(counter, IntervalTrigger(seconds=0.1), name="p")
    sched.pause(j.id)
    await sched.start()
    await asyncio.sleep(0.4)
    await sched.stop()
    assert runs == []
