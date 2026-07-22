"""Tests for the sillo.events multi-backend transport system.

Memory backend runs everywhere.  Redis / persistent / record tests skip
gracefully when the optional dependency or a running server is unavailable,
mirroring the cache backend test convention.
"""

import os

import pytest

from sillo.events import EventEmitter, EventPriority, get_transport
from sillo.events.transports.base import TransportError

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    import redis.asyncio as aioredis  # type: ignore[import-untyped]
    _have_redis = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    _have_redis = False


try:
    import tortoise  # noqa: F401
    _have_tortoise = True
except ImportError:
    _have_tortoise = False


# --------------------------------------------------------------------------
# Memory backend
# --------------------------------------------------------------------------


async def test_memory_sync_listener_receives():
    bus = EventEmitter(backend="memory")
    received = []

    @bus.on("ping")
    def handler(x):
        received.append(x)

    await bus.emit_async("ping", 42)
    assert received == [42]


async def test_memory_async_listener_is_awaited():
    bus = EventEmitter(backend="memory")
    received = []

    @bus.on("ping")
    async def handler(x):
        received.append(x)

    await bus.emit_async("ping", "hi")
    # Awaited, so the list is populated before emit returns.
    assert received == ["hi"]


async def test_memory_once_fires_only_once():
    bus = EventEmitter(backend="memory")
    hits = []

    @bus.once("tick")
    def handler():
        hits.append(1)

    await bus.emit_async("tick")
    await bus.emit_async("tick")
    assert hits == [1]


async def test_memory_priority_order():
    bus = EventEmitter(backend="memory")
    order = []

    @bus.on("e", priority=EventPriority.LOW)
    def low():
        order.append("low")

    @bus.on("e", priority=EventPriority.HIGH)
    def high():
        order.append("high")

    await bus.emit_async("e")
    assert order == ["high", "low"]


async def test_memory_namespace():
    bus = EventEmitter(backend="memory")
    ns = bus.namespace("billing")
    got = []

    @ns.on("charged")
    def handler(amount):
        got.append(amount)

    await ns.emit_async("charged", 9.99)
    assert got == [9.99]


async def test_memory_emit_sync_only_for_memory():
    bus = EventEmitter(backend="memory")
    got = []

    @bus.on("x")
    def handler(v):
        got.append(v)

    bus.emit_sync("x", 1)
    assert got == [1]


async def test_emit_sync_rejected_on_networked():
    bus = EventEmitter(backend="memory")
    with pytest.raises(RuntimeError):
        # Simulate a networked backend guard without a real server.
        bus._backend = "redis"
        bus.emit_sync("x", 1)


# --------------------------------------------------------------------------
# Transport factory
# --------------------------------------------------------------------------


def test_factory_default_is_memory():
    t = get_transport()
    assert t.name == "memory"


def test_factory_unknown_backend():
    with pytest.raises(ValueError):
        get_transport("nope")


def test_factory_record_without_tortoise_raises_transport_error():
    if not _have_tortoise:
        with pytest.raises(TransportError):
            get_transport("record")


# --------------------------------------------------------------------------
# Redis / persistent backends (require server)
# --------------------------------------------------------------------------


redis_mark = pytest.mark.skipif(
    not _have_redis, reason="redis package not installed"
)


@redis_mark
async def test_redis_cross_instance_fanout():
    try:
        client = aioredis.from_url(REDIS_URL)
        await client.ping()
        await client.flushdb()
    except Exception as exc:
        pytest.skip(f"no Redis server at {REDIS_URL}: {exc}")

    sub = EventEmitter(backend="redis", url=REDIS_URL, namespace="t")
    pub = EventEmitter(backend="redis", url=REDIS_URL, namespace="t")
    got = []

    @sub.on("hello")
    async def handler(name):
        got.append(name)

    await sub.start()
    await pub.start()
    await pub.emit_async("hello", "world")
    # Allow the pub/sub round-trip to arrive.
    for _ in range(50):
        if got:
            break
        await __import__("asyncio").sleep(0.05)
    await sub.stop()
    await pub.stop()
    assert got == ["world"]


@redis_mark
async def test_persistent_durable_delivery():
    try:
        client = aioredis.from_url(REDIS_URL)
        await client.ping()
        await client.flushdb()
    except Exception as exc:
        pytest.skip(f"no Redis server at {REDIS_URL}: {exc}")

    worker = EventEmitter(backend="persistent", url=REDIS_URL, namespace="p")
    publisher = EventEmitter(backend="persistent", url=REDIS_URL, namespace="p")
    got = []

    @worker.on("job")
    async def handler(payload):
        got.append(payload)

    await publisher.start()  # publisher pushes to backlog
    await worker.start()     # worker drains
    await publisher.emit_async("job", {"id": 1})
    for _ in range(50):
        if got:
            break
        await __import__("asyncio").sleep(0.05)
    await publisher.stop()
    await worker.stop()
    assert got == [{"id": 1}]
