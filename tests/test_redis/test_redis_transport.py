"""
RedisTransport and RedisBackend against a live server.

Skipped when no Redis is reachable. Pub/sub delivery and queue semantics are
exactly the behavior a mock cannot confirm, so these are integration tests by
design.

Like the cache tests beside them, these were written against an older API and
never corrected, because no CI job had a Redis server to run them against. The
signatures they now use are the ones the rest of the suite uses:

  * ``subscribe(channel)`` takes no handler. Delivery goes through the dispatch
    callback registered with ``bind()``, which is what the emitter does.
  * The queue backend is task-oriented: ``enqueue`` takes a ``Task``, and
    ``dequeue``/``flush``/``queue_size``/``queue_stats`` take a queue name.
  * ``is_duplicate`` and ``clear_dedup`` take a queue name and a dedup key.

They are async tests, not ``asyncio.run`` per call: a Redis client opened in
one loop cannot be used from the next.
"""

import asyncio

import pytest

from sillo.events.transports.redis import RedisTransport
from sillo.work.backends import RedisBackend
from sillo.work.task import Task, TaskResult

from ..conftest import requires_redis

pytestmark = requires_redis

QUEUE = "default"


async def noop() -> str:
    """A real coroutine function, because Task wants something it can await."""
    return "done"


def make_task(**kwargs) -> Task:
    return Task(noop, queue_name=QUEUE, **kwargs)


# ── transport lifecycle ──────────────────────────────────────────────────


async def test_start_and_stop(redis_url):
    transport = RedisTransport(url=redis_url)
    await transport.start()
    assert transport.running is True
    await transport.stop()
    assert transport.running is False


async def test_ping(redis_url):
    transport = RedisTransport(url=redis_url)
    await transport.start()
    try:
        assert await transport.ping() is True
    finally:
        await transport.stop()


async def test_stopping_a_transport_that_never_started(redis_url):
    await RedisTransport(url=redis_url).stop()


async def test_the_transport_reports_its_name(redis_url):
    assert isinstance(RedisTransport(url=redis_url).name, str)


async def test_an_error_handler_can_be_installed(redis_url):
    RedisTransport(url=redis_url).set_error_handler(lambda exc: None)


# ── publish and subscribe ────────────────────────────────────────────────


async def started(url, **kwargs):
    """A transport that records everything dispatched to it."""
    received: list = []
    transport = RedisTransport(url=url, **kwargs)

    async def dispatch(channel, envelope):
        received.append((channel, envelope))

    transport.bind(dispatch)
    await transport.start()
    return transport, received


async def test_a_published_event_reaches_a_subscriber(redis_url):
    transport, received = await started(redis_url)
    try:
        await transport.subscribe("greetings")
        await asyncio.sleep(0.2)
        await transport.publish("greetings", {"msg": "hello"})
        await asyncio.sleep(0.5)
    finally:
        await transport.stop()

    assert received, "the subscriber never fired"
    assert received[0][1]["msg"] == "hello"


async def test_a_subscriber_only_hears_its_own_channel(redis_url):
    transport, received = await started(redis_url)
    try:
        await transport.subscribe("wanted")
        await asyncio.sleep(0.2)
        await transport.publish("unwanted", {"msg": "nope"})
        await asyncio.sleep(0.4)
    finally:
        await transport.stop()

    assert received == []


async def test_namespacing_isolates_two_transports(redis_url):
    listener, heard = await started(redis_url, namespace="app-a")
    speaker = RedisTransport(url=redis_url, namespace="app-b")
    await speaker.start()
    try:
        await listener.subscribe("chan")
        await asyncio.sleep(0.2)
        await speaker.publish("chan", {"msg": "from b"})
        await asyncio.sleep(0.4)
    finally:
        await listener.stop()
        await speaker.stop()

    assert heard == [], "namespaces must not leak into each other"


# ── work backend ─────────────────────────────────────────────────────────


@pytest.fixture
async def backend(redis_url):
    # A registry is not optional for this backend: a worker in another process
    # only receives a task *name*, so without the mapping every dequeue logs
    # "not in registry" and drops the task on the floor.
    registry = {"noop": noop, "low": noop, "high": noop}
    b = RedisBackend(url=redis_url, task_registry=registry)
    try:
        yield b
    finally:
        await b.flush(QUEUE)


async def test_backend_ping(backend):
    assert await backend.ping() is True


async def test_enqueue_then_dequeue(backend):
    await backend.enqueue(make_task())
    assert await backend.dequeue(QUEUE) is not None


async def test_dequeue_on_an_empty_queue(backend):
    assert await backend.dequeue(QUEUE, timeout=0.05) is None


async def test_queue_size_tracks_enqueues(backend):
    before = await backend.queue_size(QUEUE)
    await backend.enqueue(make_task())
    assert await backend.queue_size(QUEUE) == before + 1


async def test_flush_empties_the_queue(backend):
    await backend.enqueue(make_task())
    await backend.flush(QUEUE)
    assert await backend.queue_size(QUEUE) == 0


async def test_higher_priority_comes_out_first(backend):
    """The score is built from priority, so ordering is the point of the zset."""
    from sillo.work.task import TaskPriority

    low = make_task(name="low", priority=TaskPriority.LOW)
    high = make_task(name="high", priority=TaskPriority.HIGH)
    await backend.enqueue(low)
    await backend.enqueue(high)

    first = await backend.dequeue(QUEUE)
    assert first is not None
    assert first.name == "high"


async def test_queue_stats(backend):
    stats = await backend.queue_stats(QUEUE)
    assert stats.name == QUEUE
    assert stats.size == 0


# ── results ──────────────────────────────────────────────────────────────


async def test_a_result_round_trips(backend):
    task = make_task()
    await backend.store_result(
        TaskResult(task_id=task.id, name=task.name, status=task.status)
    )
    assert await backend.get_result(task.id) is not None


async def test_a_missing_result_is_none(backend):
    assert await backend.get_result("never-ran") is None


# ── deduplication ────────────────────────────────────────────────────────


async def test_duplicate_detection(backend):
    assert await backend.is_duplicate(QUEUE, "dedup-key") is False
    assert await backend.is_duplicate(QUEUE, "dedup-key") is True


async def test_dedup_keys_are_scoped_to_their_queue(backend):
    await backend.is_duplicate(QUEUE, "shared")
    assert await backend.is_duplicate("other", "shared") is False
    await backend.clear_dedup("other", "shared")


async def test_clearing_dedup_state(backend):
    await backend.is_duplicate(QUEUE, "k")
    await backend.clear_dedup(QUEUE, "k")
    assert await backend.is_duplicate(QUEUE, "k") is False
