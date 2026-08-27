"""Tests for sillo.work.queue — connection, jobs, events, workers, middleware, batches."""

import asyncio
import time

import pytest

from sillo.work.queue import (
    Batch,
    ConnectionManager,
    Event,
    EventDispatcher,
    Job,
    JobChain,
    MemoryFailedRepository,
    PayloadSerializer,
    QRetryMiddleware,
    QTimeoutMiddleware,
    QueueWorker,
    SyncConnection,
    WorkerOptions,
    WorkerPool,
    dispatch,
    listen,
)


# ═════════════════════════════════════════════════════════════════
# Connection
# ═════════════════════════════════════════════════════════════════

class TestSyncConnection:
    def test_push_pop(self):
        async def main():
            c = SyncConnection()
            jid = await c.push("emails", '{"job":"Test"}')
            result = await c.pop("emails", timeout=1)
            assert result is not None
            assert result[0] == jid
        asyncio.run(main())

    def test_size(self):
        async def main():
            c = SyncConnection()
            await c.push("q", "{}")
            await c.push("q", "{}")
            assert await c.size("q") == 2
        asyncio.run(main())

    def test_clear(self):
        async def main():
            c = SyncConnection()
            await c.push("q", "{}")
            await c.clear("q")
            assert await c.size("q") == 0
        asyncio.run(main())

    def test_delayed_push(self):
        async def main():
            c = SyncConnection()
            await c.push("q", "{}", delay=999)
            result = await c.pop("q", timeout=0.1)
            assert result is None
        asyncio.run(main())

    def test_connection_manager(self):
        mgr = ConnectionManager()
        conn = SyncConnection()
        mgr.add("default", conn)
        assert mgr.connection("default") is conn
        with pytest.raises(KeyError):
            mgr.connection("nonexistent")


# ═════════════════════════════════════════════════════════════════
# Job
# ═════════════════════════════════════════════════════════════════

class TestJob:
    def test_job_dispatch(self):
        calls = []

        class MyJob(Job):
            queue = "test"
            def __init__(self, msg: str):
                self.msg = msg
            async def handle(self):
                calls.append(self.msg)

        job = MyJob("hello")
        asyncio.run(job.handle())
        assert calls == ["hello"]

    def test_job_with_retry_middleware(self):
        attempts = []

        class FailingJob(Job):
            tries = 3
            async def handle(self):
                attempts.append(1)
                raise ValueError("fail")

        job = FailingJob()
        with pytest.raises(ValueError):
            asyncio.run(QRetryMiddleware(max_attempts=3, base_delay=0.01, max_delay=0.1)(job.handle)())
        assert len(attempts) == 3

    def test_job_with_timeout_middleware(self):
        class SlowJob(Job):
            timeout = 0.05
            async def handle(self):
                await asyncio.sleep(1)

        job = SlowJob()
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(QTimeoutMiddleware(seconds=0.05)(job.handle)())

    def test_payload(self):
        class MyJob(Job):
            def __init__(self, x: int):
                self.x = x
            async def handle(self): pass

        job = MyJob(42)
        p = job.payload()
        # Where to import it from, not just what it is called — a bare name
        # leaves a worker with nothing to resolve.
        assert p["job"] == MyJob.job_reference()
        assert p["job"].endswith(".MyJob")
        assert "data" in p


# ═════════════════════════════════════════════════════════════════
# Events
# ═════════════════════════════════════════════════════════════════

from dataclasses import dataclass


@dataclass
class OrderShipped(Event):
    order_id: str = ""

@dataclass
class PaymentReceived(Event):
    amount: float = 0.0

class TestEvents:
    def test_dispatch_to_listener(self):
        received = []
        dispatcher = EventDispatcher()

        async def handle(event: OrderShipped):
            received.append(event.order_id)

        dispatcher.register(OrderShipped, handle)
        asyncio.run(dispatcher.dispatch(OrderShipped(order_id="42")))
        assert received == ["42"]

    def test_listen_decorator(self):
        received = []

        @listen(OrderShipped)
        async def on_shipped(event: OrderShipped):
            received.append(event.order_id)

        dispatcher = EventDispatcher()
        dispatcher.register(OrderShipped, on_shipped)
        asyncio.run(dispatcher.dispatch(OrderShipped(order_id="99")))
        assert received == ["99"]

    def test_multiple_listeners(self):
        counts = []
        dispatcher = EventDispatcher()
        for i in range(3):
            async def handler(event, i=i):
                counts.append(i)
            dispatcher.register(OrderShipped, handler)
        asyncio.run(dispatcher.dispatch(OrderShipped()))
        assert len(counts) == 3

    def test_stop_propagation(self):
        received = []
        dispatcher = EventDispatcher()

        async def first(event):
            received.append("first")
            event.stop_propagation()

        async def second(event):
            received.append("second")

        dispatcher.register(OrderShipped, first, priority=10)
        dispatcher.register(OrderShipped, second, priority=5)
        asyncio.run(dispatcher.dispatch(OrderShipped()))
        assert received == ["first"]

    def test_priority_ordering(self):
        order = []
        dispatcher = EventDispatcher()
        dispatcher.register(OrderShipped, lambda e: order.append("low"), priority=0)
        dispatcher.register(OrderShipped, lambda e: order.append("high"), priority=10)
        asyncio.run(dispatcher.dispatch(OrderShipped()))
        assert order == ["high", "low"]

    def test_forget_listener(self):
        dispatcher = EventDispatcher()
        async def h(e): pass
        dispatcher.register(OrderShipped, h)
        assert dispatcher.forget(OrderShipped, h)
        assert not dispatcher.forget(OrderShipped, h)

    def test_has_listeners(self):
        dispatcher = EventDispatcher()
        assert not dispatcher.has_listeners(OrderShipped)
        dispatcher.register(OrderShipped, lambda e: None)
        assert dispatcher.has_listeners(OrderShipped)


# ═════════════════════════════════════════════════════════════════
# Failed Jobs
# ═════════════════════════════════════════════════════════════════

class TestFailedJobs:
    def test_log_and_retrieve(self):
        async def main():
            repo = MemoryFailedRepository()
            await repo.log("emails", "j1", "SendEmail", "{}", "traceback")
            all_jobs = await repo.all()
            assert len(all_jobs) == 1
            assert all_jobs[0].job_class == "SendEmail"
            found = await repo.find("j1")
            assert found is not None
            assert await repo.forget("j1")
            assert await repo.find("j1") is None
        asyncio.run(main())

    def test_flush(self):
        async def main():
            repo = MemoryFailedRepository()
            await repo.log("q", "j1", "J", "{}", "e")
            await repo.flush()
            assert len(await repo.all()) == 0
        asyncio.run(main())

    def test_failed_job_to_dict(self):
        async def main():
            repo = MemoryFailedRepository()
            await repo.log("emails", "j1", "SendEmail", "{}", "traceback")
            found = await repo.find("j1")
            data = found.to_dict()
            assert data["id"] == "j1"
            assert data["job_class"] == "SendEmail"
        asyncio.run(main())


# ═════════════════════════════════════════════════════════════════
# Payloads
# ═════════════════════════════════════════════════════════════════

class TestPayloads:
    def test_serialize_deserialize(self):
        s = PayloadSerializer()
        payload = s.serialize("mymod.MyJob", {"x": 1, "y": "hello"}, max_tries=3)
        data = s.deserialize(payload)
        assert data["job_class"] == "mymod.MyJob"
        assert data["data"] == {"x": 1, "y": "hello"}
        assert data["max_tries"] == 3


# ═════════════════════════════════════════════════════════════════
# Batches
# ═════════════════════════════════════════════════════════════════

class TestBatches:
    def test_batch_tracks_completion(self):
        async def main():
            completed = []

            async def on_done(b):
                completed.append(True)

            batch = Batch("test", on_complete=on_done)
            batch.add("job-1")
            batch.add("job-2")
            batch.mark_complete("job-1")
            batch.mark_complete("job-2")
            await asyncio.sleep(0.05)
            assert len(completed) == 1
            assert batch.is_done
        asyncio.run(main())

    def test_batch_properties(self):
        batch = Batch("test")
        batch.add("job-1")
        batch.add("job-2")
        batch.add("job-3")
        batch.mark_complete("job-1")
        batch.mark_failed("job-2", "boom")

        assert batch.total == 3
        assert batch.completed_count == 1
        assert batch.failed_count == 1
        assert batch.is_done is True  # a failure without allow_failures ends it

    def test_batch_allows_failures_and_waits_for_every_job(self):
        async def main():
            batch = Batch("test", allow_failures=True)
            batch.add("job-1")
            batch.add("job-2")

            batch.mark_failed("job-1", "boom")
            assert not batch.is_done  # one job still outstanding

            batch.mark_complete("job-2")
            await batch.wait(timeout=1)
            assert batch.is_done
            assert batch.failed_count == 1
            assert batch.completed_count == 1

        asyncio.run(main())

    def test_finish_is_idempotent(self):
        async def main():
            calls = []

            async def on_done(b):
                calls.append(1)

            batch = Batch("test", on_complete=on_done)
            batch.add("job-1")
            batch.mark_complete("job-1")
            batch.mark_failed("job-1", "late failure after already finished")
            await asyncio.sleep(0.05)
            assert calls == [1]  # on_complete only fired once

        asyncio.run(main())

    def test_job_chain(self):
        results = []

        async def job_a():
            results.append("a")
            return "a"

        async def job_b():
            results.append("b")
            return "b"

        async def main():
            chain = JobChain()
            chain.then(job_a).then(job_b)
            out = await chain.run()
            assert out == ["a", "b"]
            assert results == ["a", "b"]
        asyncio.run(main())


# ═════════════════════════════════════════════════════════════════
# Worker
# ═════════════════════════════════════════════════════════════════

class TestQueueWorker:
    def test_worker_options_defaults(self):
        opts = WorkerOptions()
        assert opts.concurrency == 4
        assert opts.queues == ["default"]

    def test_worker_pool(self):
        assert WorkerPool() is not None
