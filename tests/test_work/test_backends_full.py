"""``sillo.work.backends`` — the memory and Redis queue backends.

The Redis half runs against ``fakeredis`` rather than skipping without a
server. ``RedisBackend._r`` returns ``self._redis`` when it is already set, so
the fake is injected there and every method under test is the real one — the
same approach ``test_redis_queue_reliability`` takes for the queue connection.
"""

import asyncio

import pytest

from sillo.work.backends import MemoryBackend, RedisBackend
from sillo.work.task import Task
from sillo.work.types import BackendUnavailable, TaskPriority, TaskResult, TaskStatus

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis  # noqa: E402


async def noop():
    """A task body. Never invoked here — these tests exercise transport."""
    return None


def make_task(name="job", queue="default", priority=TaskPriority.NORMAL, **kwargs):
    return Task(noop, name=name, queue_name=queue, priority=priority, **kwargs)


@pytest.fixture
def memory():
    return MemoryBackend()


@pytest.fixture
def redis_backend():
    backend = RedisBackend()
    backend._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # dequeue resolves the callable by name through the registry and drops
    # the task when it is missing, so every name used here is registered.
    for name in ("job", "low", "high"):
        backend.register(name, noop)
    return backend


# ── memory backend ───────────────────────────────────────────────────────


class TestMemoryQueueing:
    async def test_a_task_round_trips(self, memory):
        task = make_task()
        await memory.enqueue(task)

        popped = await memory.dequeue("default")

        assert popped.id == task.id

    async def test_higher_priority_is_served_first(self, memory):
        low = make_task(name="low", priority=TaskPriority.LOW)
        high = make_task(name="high", priority=TaskPriority.HIGH)
        await memory.enqueue(low)
        await memory.enqueue(high)

        assert (await memory.dequeue("default")).name == "high"
        assert (await memory.dequeue("default")).name == "low"

    async def test_dequeue_returns_none_once_the_timeout_passes(self, memory):
        assert await memory.dequeue("empty", timeout=0.01) is None

    async def test_dequeue_waits_for_an_arriving_task(self, memory):
        async def enqueue_soon():
            await asyncio.sleep(0.01)
            await memory.enqueue(make_task(name="late"))

        asyncio.ensure_future(enqueue_soon())
        popped = await memory.dequeue("default", timeout=1.0)

        assert popped is not None
        assert popped.name == "late"

    async def test_a_full_queue_is_refused(self):
        backend = MemoryBackend(max_size=1)
        await backend.enqueue(make_task())

        from sillo.work.types import QueueFull

        with pytest.raises(QueueFull):
            await backend.enqueue(make_task())

    async def test_queue_size_counts_what_is_waiting(self, memory):
        assert await memory.queue_size("default") == 0
        await memory.enqueue(make_task())
        assert await memory.queue_size("default") == 1

    async def test_dequeue_deadline_already_passed_by_the_time_the_lock_is_free(
        self, memory
    ):
        """A deadline can elapse before dequeue() ever gets the lock, if
        something else holds it — exercising the immediate-deadline-check
        fast path rather than the asyncio.wait_for() timeout below it."""
        memory._ensure("default")

        async with memory._locks["default"]:
            # Hold the lock past the deadline before dequeue() can even start
            # its first iteration.
            hold = asyncio.ensure_future(memory.dequeue("default", timeout=0.01))
            await asyncio.sleep(0.05)

        result = await hold
        assert result is None


class TestMemoryResults:
    async def test_a_result_round_trips(self, memory):
        result = TaskResult(task_id="t1", name="job", status=TaskStatus.COMPLETED)
        await memory.store_result(result)

        assert (await memory.get_result("t1")).task_id == "t1"

    async def test_an_unknown_result_is_none(self, memory):
        assert await memory.get_result("nope") is None


class TestMemoryDeduplication:
    async def test_the_first_claim_is_not_a_duplicate(self, memory):
        assert await memory.is_duplicate("default", "key") is False

    async def test_the_second_claim_is(self, memory):
        await memory.is_duplicate("default", "key")
        assert await memory.is_duplicate("default", "key") is True

    async def test_clearing_releases_the_key(self, memory):
        await memory.is_duplicate("default", "key")
        await memory.clear_dedup("default", "key")

        assert await memory.is_duplicate("default", "key") is False

    async def test_clearing_an_unknown_key_is_harmless(self, memory):
        await memory.clear_dedup("default", "never-seen")


class TestMemoryStats:
    async def test_stats_for_an_untouched_queue(self, memory):
        stats = await memory.queue_stats("fresh")

        assert stats.name == "fresh"
        assert stats.size == 0
        assert stats.oldest_age_ms == 0

    async def test_stats_report_the_waiting_count(self, memory):
        await memory.enqueue(make_task())

        stats = await memory.queue_stats("default")

        assert stats.size == 1
        assert stats.oldest_age_ms >= 0


# ── redis backend, against fakeredis ─────────────────────────────────────


class TestRedisQueueing:
    async def test_a_task_round_trips(self, redis_backend):
        task = make_task()
        await redis_backend.enqueue(task)

        popped = await redis_backend.dequeue("default", timeout=1)

        assert popped is not None
        assert popped.id == task.id

    async def test_higher_priority_is_served_first(self, redis_backend):
        await redis_backend.enqueue(make_task(name="low", priority=TaskPriority.LOW))
        await redis_backend.enqueue(make_task(name="high", priority=TaskPriority.HIGH))

        first = await redis_backend.dequeue("default", timeout=1)
        second = await redis_backend.dequeue("default", timeout=1)

        # BZPOPMIN with a -priority score: the higher priority sorts lower.
        assert first.name == "high"
        assert second.name == "low"

    async def test_an_empty_queue_times_out_to_none(self, redis_backend):
        assert await redis_backend.dequeue("empty", timeout=1) is None

    async def test_queue_size_counts_what_is_waiting(self, redis_backend):
        assert await redis_backend.queue_size("default") == 0
        await redis_backend.enqueue(make_task())
        assert await redis_backend.queue_size("default") == 1

    async def test_flush_empties_the_queue(self, redis_backend):
        await redis_backend.enqueue(make_task())
        await redis_backend.flush("default")

        assert await redis_backend.queue_size("default") == 0


class TestRedisResults:
    async def test_a_result_round_trips(self, redis_backend):
        await redis_backend.store_result(
            TaskResult(task_id="t1", name="job", status=TaskStatus.COMPLETED)
        )

        loaded = await redis_backend.get_result("t1")

        assert loaded is not None
        assert loaded.task_id == "t1"

    async def test_an_unknown_result_is_none(self, redis_backend):
        assert await redis_backend.get_result("nope") is None


class TestRedisDeduplication:
    async def test_the_first_claim_is_not_a_duplicate(self, redis_backend):
        assert await redis_backend.is_duplicate("default", "key") is False

    async def test_the_second_claim_is(self, redis_backend):
        await redis_backend.is_duplicate("default", "key")
        assert await redis_backend.is_duplicate("default", "key") is True

    async def test_clearing_releases_the_key(self, redis_backend):
        await redis_backend.is_duplicate("default", "key")
        await redis_backend.clear_dedup("default", "key")

        assert await redis_backend.is_duplicate("default", "key") is False


class TestRedisStatsAndHealth:
    async def test_ping_succeeds_against_a_live_server(self, redis_backend):
        assert await redis_backend.ping() is True

    async def test_stats_report_the_waiting_count(self, redis_backend):
        await redis_backend.enqueue(make_task())

        stats = await redis_backend.queue_stats("default")

        assert stats.name == "default"
        assert stats.size == 1


class TestRedisRegistration:
    def test_a_task_function_can_be_registered(self):
        backend = RedisBackend()

        def handler():
            return None

        backend.register("job", handler)

        assert backend._registry["job"] is handler

    def test_a_registry_can_be_supplied(self):
        registry = {"existing": object()}
        assert RedisBackend(task_registry=registry)._registry is registry


class TestRedisUnavailable:
    async def test_a_dead_server_reports_backend_unavailable(self):
        backend = RedisBackend(url="redis://127.0.0.1:1/0")

        with pytest.raises(BackendUnavailable):
            await backend._r()

    async def test_a_failing_command_is_reported_as_unavailable(self, redis_backend):
        class Broken:
            async def bzpopmin(self, *a, **k):
                raise RuntimeError("connection reset")

        redis_backend._redis = Broken()

        with pytest.raises(BackendUnavailable):
            await redis_backend.dequeue("default", timeout=1)

    async def test_r_raises_import_error_without_the_redis_package(self, monkeypatch):
        import sillo.work.backends as backends_module

        monkeypatch.setattr(backends_module, "aioredis", None)
        backend = RedisBackend()

        with pytest.raises(ImportError, match="redis is required"):
            await backend._r()

    async def test_r_connects_and_caches_the_client(self, monkeypatch):
        import sillo.work.backends as backends_module

        fake_server = fakeredis.aioredis.FakeRedis(decode_responses=True)

        class FakeAioredisModule:
            @staticmethod
            def from_url(url, decode_responses=True, socket_timeout=None):
                return fake_server

        monkeypatch.setattr(backends_module, "aioredis", FakeAioredisModule)
        backend = RedisBackend()

        r = await backend._r()
        assert r is fake_server
        assert await backend._r() is fake_server  # cached on the second call

    async def test_dequeue_times_out_when_the_command_itself_hangs(self):
        backend = RedisBackend()

        class HangingRedis:
            async def bzpopmin(self, *a, **k):
                await asyncio.sleep(10)

        backend._redis = HangingRedis()

        result = await backend.dequeue("default", timeout=0.01)
        assert result is None

    async def test_dequeue_drops_a_corrupt_payload(self, redis_backend):
        key = f"{redis_backend.prefix}q:default"
        await redis_backend._redis.zadd(key, {"not-valid-json{{{": 0})

        assert await redis_backend.dequeue("default", timeout=1) is None

    async def test_dequeue_drops_a_payload_for_an_unregistered_task_name(
        self, redis_backend
    ):
        task = make_task(name="not-in-registry")
        # Bypass register(): this name was never added to the fixture's registry.
        del redis_backend._registry["job"], redis_backend._registry["low"]
        del redis_backend._registry["high"]
        await redis_backend.enqueue(task)

        assert await redis_backend.dequeue("default", timeout=1) is None

    async def test_ping_reports_false_when_the_server_is_unreachable(self):
        backend = RedisBackend(url="redis://127.0.0.1:1/0")
        assert await backend.ping() is False
