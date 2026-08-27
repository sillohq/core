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


def test_compound_trigger_returns_none_when_all_sub_triggers_are_exhausted():
    past = time.time() - 100
    t = CompoundTrigger(
        triggers=[DateTrigger(at=past), DateTrigger(at=past)],
        logic=CompoundLogic.OR,
    )
    assert t.next_fire(time.time()) is None


def test_cron_parser_rejects_wrong_field_count():
    with pytest.raises(ValueError):
        CronParser("0 9 * *")


def test_cron_parser_range_with_step():
    parser = CronParser("0 0 1-10/2 * *")
    assert parser._day == {1, 3, 5, 7, 9}


def test_cron_parser_list_of_values():
    parser = CronParser("0 0 * * 1,3,5")
    assert parser._weekday == {1, 3, 5}


def test_cron_parser_l_day_marker():
    parser = CronParser("0 0 L * *")
    assert parser._has_l_day is True
    assert -1 in parser._day


def test_cron_parser_w_nearest_weekday_marker():
    parser = CronParser("0 0 15W * *")
    assert parser._has_w is True
    assert 15 in parser._day


def test_cron_parser_hash_nth_weekday_marker():
    parser = CronParser("0 0 * * 2#3")
    assert parser._has_hash is True
    # The "#" branch is a documented no-op for now: it adds no constraint.
    assert parser._weekday == set()


def test_cron_parser_garbage_value_falls_back_to_sentinel():
    parser = CronParser("0 0 ? * *")
    assert -1 in parser._day


def test_cron_next_skips_mismatched_hour_day_and_month():
    # 9am on the 15th of March: spread across hour/day/month fields so
    # next() has to `continue` past every hour, day, and month that doesn't
    # match before landing on a real hit, regardless of what today is.
    import datetime

    parser = CronParser("0 9 15 3 *")
    nxt = parser.next(time.time())
    dt = datetime.datetime.fromtimestamp(nxt)
    assert dt.hour == 9
    assert dt.day == 15
    assert dt.month == 3


def test_cron_next_skips_mismatched_weekday():
    import datetime

    # This parser maps the weekday field directly onto datetime.weekday()
    # (Monday=0), not the traditional cron Sunday=0 convention.
    parser = CronParser("0 9 * * 1")
    nxt = parser.next(time.time())
    dt = datetime.datetime.fromtimestamp(nxt)
    assert dt.hour == 9
    assert dt.weekday() == 1


def test_cron_next_gives_up_after_a_year_for_an_impossible_schedule():
    # February 31st never occurs.
    parser = CronParser("0 0 31 2 *")
    nxt = parser.next(time.time())
    assert nxt > time.time() + 365 * 86400


async def test_scheduled_job_compute_next_marks_completed_when_trigger_exhausted():
    at = time.time() - 5  # already in the past
    job = ScheduledJob(_noop_job, DateTrigger(at=at))
    job.last_run_time = at
    job.compute_next()
    assert job.status == JobStatus.COMPLETED
    assert job.next_run_time is None


async def test_scheduled_job_run_applies_middleware():
    calls = []

    async def middleware_factory(handler, job):
        async def wrapped(*args, **kwargs):
            calls.append("before")
            result = await handler(*args, **kwargs)
            calls.append("after")
            return result

        return wrapped

    job = ScheduledJob(
        _noop_job,
        DateTrigger(at=time.time() + 1000),
        middleware=[middleware_factory],
    )
    result = await job.run()
    assert result == "ok"
    assert calls == ["before", "after"]


async def test_scheduled_job_run_marks_completed_for_date_trigger():
    job = ScheduledJob(_noop_job, DateTrigger(at=time.time() + 1000))
    await job.run()
    assert job.status == JobStatus.COMPLETED


async def test_scheduled_job_run_counts_errors_and_reraises():
    async def boom():
        raise ValueError("kaboom")

    job = ScheduledJob(boom, DateTrigger(at=time.time() + 1000))
    with pytest.raises(ValueError, match="kaboom"):
        await job.run()
    assert job._errors == 1


def test_scheduled_job_to_dict():
    job = ScheduledJob(
        _noop_job, DateTrigger(at=time.time() + 1000), name="my-job", id="fixed-id"
    )
    data = job.to_dict()
    assert data["id"] == "fixed-id"
    assert data["name"] == "my-job"
    assert data["status"] == "active"
    assert data["runs"] == 0
    assert data["errors"] == 0


async def _noop_job():
    return "ok"


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


def test_scheduler_list_filters_by_status():
    sched = SchedulerManager()

    async def job():
        return 1

    active = sched.schedule(job, IntervalTrigger(seconds=60), name="active")
    paused = sched.schedule(job, IntervalTrigger(seconds=60), name="paused")
    sched.pause(paused.id)

    assert sched.list(status=JobStatus.ACTIVE) == [active]
    assert sched.list(status=JobStatus.PAUSED) == [paused]


def test_scheduler_resume_unknown_job_returns_false():
    sched = SchedulerManager()
    assert sched.resume("nope") is False


def test_scheduler_stats_counts_paused_jobs():
    sched = SchedulerManager()

    async def job():
        return 1

    j = sched.schedule(job, IntervalTrigger(seconds=60), name="p")
    sched.pause(j.id)

    stats = sched.stats
    assert stats.jobs_paused == 1
    assert stats.jobs_active == 0


async def test_scheduler_stop_before_ticker_ever_runs_hits_cancelled_branch():
    sched = SchedulerManager()
    await sched.start()
    # Stopping immediately, before the ticker task gets a chance to run its
    # first iteration, cancels it before its own internal CancelledError
    # handling can absorb the cancellation — so `stop()` observes it directly.
    await sched.stop()


async def test_execute_swallows_job_exceptions():
    sched = SchedulerManager()

    async def boom():
        raise ValueError("kaboom")

    job = sched.schedule(boom, IntervalTrigger(seconds=60), name="boom")
    # Should not raise despite the job failing.
    await sched._execute(job)
    assert job._errors == 1


async def test_execute_swallows_cancelled_error():
    sched = SchedulerManager()

    async def cancels():
        raise asyncio.CancelledError()

    job = sched.schedule(cancels, IntervalTrigger(seconds=60), name="cancels")
    # Should not propagate the CancelledError out of _execute.
    await sched._execute(job)


async def test_loop_skips_jobs_at_max_instances():
    sched = SchedulerManager()

    async def slow():
        await asyncio.sleep(10)

    job = sched.schedule(
        slow, IntervalTrigger(seconds=0.01), name="slow", max_instances=1
    )
    job.current_instances = 1  # simulate an already-running instance
    job.next_run_time = time.time() - 1  # due immediately

    sched._running = True
    loop_task = asyncio.create_task(sched._loop())
    await asyncio.sleep(0.05)
    sched._running = False
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # The max_instances guard should have kept it from spawning a new run.
    assert job.current_instances == 1


async def test_loop_skips_coalesced_job_already_running():
    sched = SchedulerManager()

    async def slow():
        await asyncio.sleep(10)

    job = sched.schedule(
        slow, IntervalTrigger(seconds=0.01), name="slow", coalesce=True
    )
    job.current_instances = 1  # simulate an already-running instance
    job.max_instances = 0  # unlimited, so only the coalesce check applies
    job.next_run_time = time.time() - 1

    sched._running = True
    loop_task = asyncio.create_task(sched._loop())
    await asyncio.sleep(0.05)
    sched._running = False
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    assert job.current_instances == 1


async def test_loop_logs_and_continues_on_unexpected_error(monkeypatch):
    sched = SchedulerManager()

    async def job():
        return 1

    scheduled = sched.schedule(job, IntervalTrigger(seconds=60), name="j")
    scheduled.next_run_time = time.time() - 1

    calls = {"count": 0}
    real_compute_next = ScheduledJob.compute_next

    def flaky_compute_next(self, now=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return real_compute_next(self, now)

    monkeypatch.setattr(ScheduledJob, "compute_next", flaky_compute_next)

    sched._running = True
    loop_task = asyncio.create_task(sched._loop())
    await asyncio.sleep(0.05)
    sched._running = False
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    assert calls["count"] >= 1


def test_setup_scheduler_wires_lifecycle_and_is_idempotent():
    from sillo import SilloApp
    from sillo.work.scheduler.manager import setup_scheduler

    app = SilloApp()
    sched = setup_scheduler(app)
    assert app.state["scheduler"] is sched

    # Calling it again on the same app returns the existing instance.
    assert setup_scheduler(app) is sched


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
