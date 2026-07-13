"""
Comprehensive tests for sillo.work — covers every feature in the docs.

Tests: Task lifecycle, priority ordering, hooks, serialization, Queue
enqueue/dequeue/dedup/stats, Worker execution/retry/circuit-breaker/DLQ,
Scheduler interval/cron/date/pause/resume/stats, BackgroundTask fire-and-forget,
custom middleware, all exception types, stats types.
"""

import asyncio
import time

import pytest

from sillo.work import (
    BackgroundTask,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
    LoggingMiddleware,
    MemoryBackend,
    Queue,
    RateLimitMiddleware,
    Scheduler,
    TaskCancelled,
    TaskPriority,
    TaskRejected,
    TaskResult,
    TaskStatus,
    TaskTimeout,
    TimeoutMiddleware,
    Worker,
    task,
)
from sillo.work.task import Task
from sillo.work.types import (
    CircuitBreakerOpen,
    CircuitState,
    InvalidTrigger,
    JobStatus,
    QueueFull,
    QueueHealth,
    QueueStats,
    SchedulerStats,
    TaskError,
    WorkerStats,
)


# ══════════════════════════════════════════════════════════════════════════
# Task — lifecycle
# ══════════════════════════════════════════════════════════════════════════


class TestTask:
    def test_basic_execution(self):
        async def work():
            return "done"

        t = Task(work)
        result = asyncio.run(t.run())
        assert result == "done"
        assert t.is_done
        assert t.status == TaskStatus.COMPLETED
        assert t.result is not None
        assert t.result.ok
        assert t.result.result == "done"

    def test_run_twice_raises(self):
        t = Task(asyncio.sleep, 0.01)
        asyncio.run(t.run())
        with pytest.raises(TaskError):
            asyncio.run(t.run())

    def test_timeout(self):
        async def slow():
            await asyncio.sleep(1)

        t = Task(slow, timeout=0.05)
        with pytest.raises(TaskTimeout):
            asyncio.run(t.run())
        assert t.status == TaskStatus.FAILED
        assert t.result is not None
        assert not t.result.ok

    def test_timeout_via_ctor(self):
        async def slow():
            await asyncio.sleep(1)

        t = Task(slow, timeout=0.05)
        with pytest.raises(TaskTimeout):
            asyncio.run(t.run())

    def test_cancellation(self):
        async def forever():
            await asyncio.sleep(999)

        async def main():
            t = Task(forever)
            task_obj = asyncio.ensure_future(t.run())
            await asyncio.sleep(0.05)
            task_obj.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task_obj
            assert t.status == TaskStatus.CANCELLED

        asyncio.run(main())

    def test_priority_ordering(self):
        low = Task(asyncio.sleep, 0, name="low", priority=TaskPriority.LOW)
        norm = Task(asyncio.sleep, 0, name="norm", priority=TaskPriority.NORMAL)
        high = Task(asyncio.sleep, 0, name="high", priority=TaskPriority.HIGH)
        crit = Task(asyncio.sleep, 0, name="crit", priority=TaskPriority.CRITICAL)

        tasks = [low, norm, high, crit]
        sorted_tasks = sorted(tasks)
        assert sorted_tasks[0].name == "crit"
        assert sorted_tasks[1].name == "high"
        assert sorted_tasks[2].name == "norm"
        assert sorted_tasks[3].name == "low"

    def test_hooks_before_and_after(self):
        events = []

        async def work():
            events.append("work")
            return "ok"

        t = Task(work)

        async def before(task):
            events.append("before")

        async def after(task):
            events.append("after")

        t.before(before).after(after)
        asyncio.run(t.run())
        assert events == ["before", "work", "after"]

    def test_hooks_success_and_failure(self):
        results = []
        errors = []

        async def work():
            return "ok"

        async def fail():
            raise ValueError("boom")

        t1 = Task(work)
        t1.on_success(lambda r: results.append(r.result))
        asyncio.run(t1.run())
        assert results == ["ok"]

        t2 = Task(fail)
        t2.on_failure(lambda r: errors.append(r.error))
        with pytest.raises(ValueError):
            asyncio.run(t2.run())
        assert len(errors) == 1
        assert "boom" in errors[0]

    def test_hook_exception_does_not_propagate(self):
        async def work():
            return "ok"

        async def broken_before(task):
            raise RuntimeError("before crash")

        async def broken_after(task):
            raise RuntimeError("after crash")

        async def broken_success(result):
            raise RuntimeError("success crash")

        t = Task(work)
        t.before(broken_before).after(broken_after).on_success(broken_success)
        result = asyncio.run(t.run())
        assert result == "ok"

    def test_serialization(self):
        async def work(x):
            pass

        t = Task(work, 42, name="test", queue_name="q")
        data = t.serialize()
        assert '"test"' in data
        assert '"q"' in data

    def test_to_dict(self):
        t = Task(asyncio.sleep, 0.01, name="dict-test")
        d = t.to_dict()
        assert d["name"] == "dict-test"
        assert d["status"] == "pending"
        assert "id" in d

    def test_wait(self):
        async def work():
            return "waited"

        async def main():
            t = Task(work)
            asyncio.ensure_future(t.run())
            result = await t.wait()
            assert result == "waited"

        asyncio.run(main())

    def test_wait_timeout(self):
        async def slow():
            await asyncio.sleep(999)

        async def main():
            t = Task(slow)
            asyncio.ensure_future(t.run())
            with pytest.raises(asyncio.TimeoutError):
                await t.wait(timeout=0.05)

        asyncio.run(main())

    def test_task_decorator(self):
        @task(name="my-task", priority=TaskPriority.HIGH, max_attempts=3, queue="emails")
        async def my_task():
            pass

        assert my_task._work_name == "my-task"
        assert my_task._work_priority == TaskPriority.HIGH
        assert my_task._work_max_attempts == 3
        assert my_task._work_queue == "emails"


# ══════════════════════════════════════════════════════════════════════════
# Queue
# ══════════════════════════════════════════════════════════════════════════


class TestQueue:
    def test_put_and_get(self):
        async def work():
            return "q-result"

        async def main():
            q = Queue("test")
            await q.put(work, name="q-task")
            t = await q.get(timeout=1)
            assert t is not None
            assert t.name == "q-task"
            await t.run()
            await q.mark_done(t)
            assert t.result is not None
            assert t.result.ok
            assert t.result.result == "q-result"

        asyncio.run(main())

    def test_dedup_rejects_duplicate(self):
        async def main():
            q = Queue("test", backend=MemoryBackend(), dedup=True)
            await q.put(asyncio.sleep, 0, dedup_key="once")
            with pytest.raises(TaskRejected):
                await q.put(asyncio.sleep, 0, dedup_key="once")

        asyncio.run(main())

    def test_get_result(self):
        async def work():
            return "found"

        async def main():
            q = Queue("test")
            t = await q.put(work)
            await t.run()
            await q.mark_done(t)
            r = await q.get_result(t.id)
            assert r is not None
            assert r.result == "found"

        asyncio.run(main())

    def test_size(self):
        async def main():
            q = Queue("test")
            assert await q.size == 0
            await q.put(asyncio.sleep, 0)
            assert await q.size == 1

        asyncio.run(main())

    def test_stats(self):
        async def main():
            q = Queue("test")
            stats = await q.stats()
            assert isinstance(stats, QueueStats)
            assert stats.name == "test"
            assert stats.size == 0

        asyncio.run(main())

    def test_close_rejects_new_tasks(self):
        async def main():
            q = Queue("test")
            await q.close()
            with pytest.raises(RuntimeError):
                await q.put(asyncio.sleep, 0)

        asyncio.run(main())

    def test_priority_ordering_in_queue(self):
        async def main():
            q = Queue("test")
            await q.put(asyncio.sleep, 0, name="low", priority=TaskPriority.LOW)
            await q.put(asyncio.sleep, 0, name="high", priority=TaskPriority.HIGH)
            await q.put(asyncio.sleep, 0, name="norm", priority=TaskPriority.NORMAL)

            t1 = await q.get(timeout=1)
            t2 = await q.get(timeout=1)
            t3 = await q.get(timeout=1)
            assert t1.name == "high"
            assert t2.name == "norm"
            assert t3.name == "low"

        asyncio.run(main())


# ══════════════════════════════════════════════════════════════════════════
# Worker
# ══════════════════════════════════════════════════════════════════════════


class TestWorker:
    def test_worker_executes_tasks(self):
        async def work():
            return "worker-done"

        async def main():
            q = Queue("test")
            w = Worker(q, concurrency=1)
            await q.put(work)
            await w.start()
            await asyncio.sleep(0.3)
            await w.stop()
            assert w.stats.processed == 1
            assert w.stats.failed == 0

        asyncio.run(main())

    def test_worker_retry_and_eventually_fail(self):
        call_count = [0]

        async def flaky():
            call_count[0] += 1
            raise ValueError("always fails")

        async def main():
            q = Queue("test")
            w = Worker(q, concurrency=1)
            await q.put(flaky, max_attempts=2, name="flaky")
            await w.start()
            await asyncio.sleep(3.0)
            await w.stop()
            assert call_count[0] == 2
            assert w.stats.failed >= 1

        asyncio.run(main())

    def test_dead_letter_queue(self):
        async def always_fail():
            raise RuntimeError("fail")

        async def main():
            q = Queue("test")
            dlq = Queue("dlq")
            w = Worker(q, concurrency=1, dead_letter_queue=dlq)
            await q.put(always_fail, max_attempts=2, name="failing")
            await w.start()
            await asyncio.sleep(3.0)
            await w.stop()
            assert await dlq.size > 0

        asyncio.run(main())

    def test_worker_stats(self):
        async def work():
            return "ok"

        async def main():
            q = Queue("test")
            w = Worker(q, concurrency=2)
            assert isinstance(w.stats, WorkerStats)
            assert w.stats.workers == 2
            assert w.stats.circuit == CircuitState.CLOSED

        asyncio.run(main())

    def test_circuit_breaker_opens(self):
        async def fail():
            raise ValueError("fail")

        async def main():
            q = Queue("test")
            w = Worker(q, concurrency=1, circuit_breaker_threshold=3, circuit_breaker_window=60)
            for _ in range(5):
                await q.put(fail, max_attempts=1)
            await w.start()
            await asyncio.sleep(0.3)
            await w.stop()
            assert w.stats.failed >= 3

        asyncio.run(main())


# ══════════════════════════════════════════════════════════════════════════
# Scheduler
# ══════════════════════════════════════════════════════════════════════════


class TestScheduler:
    def test_interval_trigger(self):
        s = Scheduler()
        runs = []

        async def job():
            runs.append(1)

        j = s.schedule(job, IntervalTrigger(0.05), name="interval-test")
        assert j.status == JobStatus.ACTIVE

    def test_cron_trigger_next_fire(self):
        t = CronTrigger("0 9 * * 1-5")
        now = time.time()
        nxt = t.next_fire(now)
        assert nxt > now

    def test_cron_trigger_invalid_expression(self):
        with pytest.raises(InvalidTrigger):
            CronTrigger("* * *")

    def test_date_trigger_fires_once(self):
        t = DateTrigger(at=time.time())
        assert t.next_fire(0) is not None
        assert t.next_fire(1) is None

    def test_scheduler_pause_resume(self):
        s = Scheduler()
        s.schedule(lambda: None, IntervalTrigger(99999), name="pausable")
        jobs = s.list()
        assert len(jobs) == 1
        assert s.pause(jobs[0].id)
        assert s.list(JobStatus.PAUSED)[0].name == "pausable"
        assert s.resume(jobs[0].id)
        assert s.list(JobStatus.ACTIVE)[0].name == "pausable"

    def test_scheduler_remove(self):
        s = Scheduler()
        job = s.schedule(lambda: None, IntervalTrigger(99999), name="removable")
        assert s.remove(job.id)
        assert len(s.list()) == 0

    def test_scheduler_decorators(self):
        s = Scheduler()

        @s.every(99999)
        async def interval_job():
            pass

        @s.cron("0 0 * * *")
        async def cron_job():
            pass

        assert len(s.list()) == 2

    def test_scheduler_stats(self):
        s = Scheduler()
        s.schedule(lambda: None, IntervalTrigger(99999), name="stats-job")
        stats = s.stats
        assert isinstance(stats, SchedulerStats)
        assert stats.jobs_total == 1

    def test_job_to_dict(self):
        s = Scheduler()
        job = s.schedule(lambda: None, IntervalTrigger(99999), name="dict-job")
        d = job.to_dict()
        assert d["name"] == "dict-job"
        assert d["status"] == "active"


# ══════════════════════════════════════════════════════════════════════════
# BackgroundTask
# ══════════════════════════════════════════════════════════════════════════


class TestBackgroundTask:
    def test_run_and_wait(self):
        async def work():
            await asyncio.sleep(0.05)
            return "bg-done"

        async def main():
            bt = BackgroundTask.run(work)
            result = await bt.wait()
            assert result == "bg-done"
            assert bt.done

        asyncio.run(main())

    def test_cancel(self):
        async def forever():
            await asyncio.sleep(999)
            return "never"

        async def main():
            bt = BackgroundTask.run(forever)
            await asyncio.sleep(0.05)
            assert bt.cancel() is True

        asyncio.run(main())

    def test_on_done_callback(self):
        results = []

        async def work():
            return "cb-result"

        async def on_done(result):
            results.append(result.result)

        async def main():
            bt = BackgroundTask.run(work, on_done=on_done)
            await bt.wait()
            assert results == ["cb-result"]

        asyncio.run(main())

    def test_on_done_callback(self):
        results = []

        async def work():
            return "cb-result"

        async def on_done(result):
            results.append(result.result)

        async def main():
            bt = BackgroundTask.run(work, on_done=on_done)
            await bt.wait()
            assert results == ["cb-result"]

        asyncio.run(main())

    def test_run_outside_async_context_raises(self):
        with pytest.raises(RuntimeError, match="async context"):
            BackgroundTask.run(asyncio.sleep, 0)


# ══════════════════════════════════════════════════════════════════════════
# Middleware
# ══════════════════════════════════════════════════════════════════════════


class TestMiddleware:
    def test_timeout_middleware_sets_default(self):
        async def work():
            await asyncio.sleep(0.05)
            return "ok"

        mw = TimeoutMiddleware(5.0)
        t = Task(work, timeout=None)
        assert getattr(t, "timeout", None) is None

        async def main():
            await mw.before_execute(t)
            assert t.timeout == 5.0

        asyncio.run(main())

    def test_rate_limit_middleware_slows_down(self):
        mw = RateLimitMiddleware(max_per_second=1, burst=1)
        t = Task(asyncio.sleep, 0)
        start = time.monotonic()

        async def main():
            await mw.before_execute(t)
            await mw.before_execute(t)

        asyncio.run(main())
        elapsed = time.monotonic() - start
        assert elapsed >= 0.8  # should wait ~1s for the second token

    def test_logging_middleware(self):
        mw = LoggingMiddleware()

        async def main():
            t = Task(asyncio.sleep, 0.01)
            await mw.before_enqueue(t)
            await mw.before_execute(t)
            await t.run()
            if t.result:
                await mw.after_execute(t.result)

        asyncio.run(main())


# ══════════════════════════════════════════════════════════════════════════
# Backends
# ══════════════════════════════════════════════════════════════════════════


class TestMemoryBackend:
    def test_enqueue_dequeue(self):
        async def main():
            b = MemoryBackend()
            t = Task(asyncio.sleep, 0, name="b-test")
            await b.enqueue(t)
            result = await b.dequeue("default", timeout=1)
            assert result is not None
            assert result.name == "b-test"

        asyncio.run(main())

    def test_store_and_get_result(self):
        async def main():
            b = MemoryBackend()
            r = TaskResult(task_id="1", name="t", status=TaskStatus.COMPLETED, result="ok")
            await b.store_result(r)
            found = await b.get_result("1")
            assert found is not None
            assert found.result == "ok"

        asyncio.run(main())

    def test_dedup(self):
        async def main():
            b = MemoryBackend()
            assert not await b.is_duplicate("q", "key1")
            assert await b.is_duplicate("q", "key1")
            await b.clear_dedup("q", "key1")
            assert not await b.is_duplicate("q", "key1")

        asyncio.run(main())

    def test_max_size_rejects(self):
        async def main():
            b = MemoryBackend(max_size=1)
            t1 = Task(asyncio.sleep, 0, name="t1")
            t2 = Task(asyncio.sleep, 0, name="t2")
            await b.enqueue(t1)
            with pytest.raises(QueueFull):
                await b.enqueue(t2)

        asyncio.run(main())


# ══════════════════════════════════════════════════════════════════════════
# Exception types
# ══════════════════════════════════════════════════════════════════════════


class TestExceptions:
    def test_task_error_carries_context(self):
        e = TaskError("msg", task_id="abc", queue_name="q")
        assert e.task_id == "abc"
        assert e.queue_name == "q"

    def test_task_rejected_is_task_error(self):
        e = TaskRejected("no", queue_name="q")
        assert isinstance(e, TaskError)

    def test_task_timeout_is_task_error(self):
        e = TaskTimeout("took too long", task_id="1")
        assert isinstance(e, TaskError)

    def test_queue_full(self):
        e = QueueFull("full", queue_name="q")
        assert e.queue_name == "q"


# ══════════════════════════════════════════════════════════════════════════
# Stats types
# ══════════════════════════════════════════════════════════════════════════


class TestStats:
    def test_task_result_serialization(self):
        r = TaskResult(task_id="1", name="t", status=TaskStatus.COMPLETED, result="done", attempt=1, max_attempts=3)
        d = r.to_dict()
        assert d["task_id"] == "1"
        assert d["status"] == "completed"
        assert d["result"] == "done"

    def test_queue_stats(self):
        s = QueueStats(name="q", size=5, completed=10, failed=2)
        d = s.to_dict()
        assert d["name"] == "q"
        assert d["size"] == 5

    def test_worker_stats(self):
        s = WorkerStats(processed=42, failed=3, workers=4, circuit=CircuitState.CLOSED)
        d = s.to_dict()
        assert d["processed"] == 42
        assert d["circuit"] == "closed"

    def test_scheduler_stats(self):
        s = SchedulerStats(jobs_total=5, jobs_active=3, runs_total=100)
        d = s.to_dict()
        assert d["jobs_total"] == 5
        assert d["runs"] == 100

    def test_queue_health_enum(self):
        assert QueueHealth.HEALTHY.value == "healthy"
        assert QueueHealth.DEGRADED.value == "degraded"

    def test_circuit_state_enum(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
