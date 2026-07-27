"""
RedisTransport and RedisBackend against a live server.

Skipped when no Redis is reachable. Pub/sub delivery and queue semantics are
exactly the behavior a mock cannot confirm, so these are integration tests by
design.
"""

import asyncio

import pytest

from sillo.events.transports.redis import RedisTransport
from sillo.work.backends import RedisBackend

from ..conftest import requires_redis

pytestmark = requires_redis


def _run(coro):
    return asyncio.run(coro)


# ── transport lifecycle ──────────────────────────────────────────────────


def test_start_and_stop(redis_url):
    async def scenario():
        t = RedisTransport(url=redis_url)
        await t.start()
        running = t.running
        await t.stop()
        return running, t.running

    started, stopped = _run(scenario())
    assert started is True
    assert stopped is False


def test_ping(redis_url):
    async def scenario():
        t = RedisTransport(url=redis_url)
        await t.start()
        try:
            return await t.ping()
        finally:
            await t.stop()

    assert _run(scenario()) is not False


def test_stopping_a_transport_that_never_started(redis_url):
    _run(RedisTransport(url=redis_url).stop())


def test_the_transport_reports_its_name(redis_url):
    assert isinstance(RedisTransport(url=redis_url).name, str)


# ── publish and subscribe ────────────────────────────────────────────────


def test_a_published_event_reaches_a_subscriber(redis_url):
    received = []

    async def scenario():
        t = RedisTransport(url=redis_url)
        await t.start()
        try:
            await t.subscribe("greetings", lambda evt: received.append(evt))
            await asyncio.sleep(0.2)
            await t.publish("greetings", {"msg": "hello"})
            await asyncio.sleep(0.5)
        finally:
            await t.stop()

    _run(scenario())
    assert received, "the subscriber never fired"


def test_a_subscriber_only_hears_its_own_channel(redis_url):
    heard = []

    async def scenario():
        t = RedisTransport(url=redis_url)
        await t.start()
        try:
            await t.subscribe("wanted", lambda evt: heard.append(evt))
            await asyncio.sleep(0.2)
            await t.publish("unwanted", {"msg": "nope"})
            await asyncio.sleep(0.4)
        finally:
            await t.stop()

    _run(scenario())
    assert heard == []


def test_namespacing_isolates_two_transports(redis_url):
    heard = []

    async def scenario():
        a = RedisTransport(url=redis_url, namespace="app-a")
        b = RedisTransport(url=redis_url, namespace="app-b")
        await a.start()
        await b.start()
        try:
            await a.subscribe("chan", lambda evt: heard.append(evt))
            await asyncio.sleep(0.2)
            await b.publish("chan", {"msg": "from b"})
            await asyncio.sleep(0.4)
        finally:
            await a.stop()
            await b.stop()

    _run(scenario())
    assert heard == [], "namespaces must not leak into each other"


def test_an_error_handler_can_be_installed(redis_url):
    t = RedisTransport(url=redis_url)
    t.set_error_handler(lambda exc: None)


# ── work backend ─────────────────────────────────────────────────────────


@pytest.fixture
def backend(redis_url):
    b = RedisBackend(url=redis_url)
    yield b
    _run(b.flush())


def test_backend_ping(backend):
    assert _run(backend.ping()) is not False


def test_enqueue_then_dequeue(backend):
    async def scenario():
        await backend.enqueue({"task": "send_email", "args": [1]})
        return await backend.dequeue()

    assert _run(scenario()) is not None


def test_dequeue_on_an_empty_queue(backend):
    assert _run(backend.dequeue()) is None


def test_queue_size_tracks_enqueues(backend):
    async def scenario():
        before = await backend.queue_size()
        await backend.enqueue({"task": "t"})
        return before, await backend.queue_size()

    before, after = _run(scenario())
    assert after == before + 1


def test_flush_empties_the_queue(backend):
    async def scenario():
        await backend.enqueue({"task": "t"})
        await backend.flush()
        return await backend.queue_size()

    assert _run(scenario()) == 0


def test_queue_stats(backend):
    assert isinstance(_run(backend.queue_stats()), dict)


def test_a_result_round_trips(backend):
    async def scenario():
        await backend.store_result("job-1", {"ok": True})
        return await backend.get_result("job-1")

    assert _run(scenario()) is not None


def test_a_missing_result_is_none(backend):
    assert _run(backend.get_result("never-ran")) is None


def test_duplicate_detection(backend):
    async def scenario():
        first = await backend.is_duplicate("dedup-key")
        second = await backend.is_duplicate("dedup-key")
        return first, second

    first, second = _run(scenario())
    assert first != second, "the second submission should be seen as a duplicate"


def test_clearing_dedup_state(backend):
    async def scenario():
        await backend.is_duplicate("k")
        await backend.clear_dedup("k")
        return await backend.is_duplicate("k")

    assert _run(scenario()) is False
