"""``EventEmitter`` — the paths around transports, namespaces and lifecycle.

The emitter is mostly covered through the memory backend. What was not reached
is everything that only matters once a networked transport is involved:
subscribing before a loop exists, subscribing after ``start()``, the default
error handler, and the namespace helper.
"""

import asyncio

import pytest

from sillo.events.emitter import EventEmitter, EventNamespace
from sillo.events.transports.base import BaseTransport


class RecordingTransport(BaseTransport):
    """A transport that records what it was asked to do."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.published = []
        self.subscribed = []
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True
        await super().start()

    async def stop(self):
        self.stopped = True
        await super().stop()

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def publish(self, channel, envelope):
        self.published.append((channel, envelope))
        await self._deliver(channel, envelope)


@pytest.fixture
def transport():
    return RecordingTransport()


@pytest.fixture
def emitter(transport):
    return EventEmitter(transport=transport)


class TestConstruction:
    def test_an_explicit_transport_is_used(self, transport):
        assert EventEmitter(transport=transport).transport is transport

    def test_a_backend_name_builds_one(self):
        from sillo.events.transports.memory import MemoryTransport

        assert isinstance(EventEmitter(backend="memory").transport, MemoryTransport)

    def test_the_default_backend_is_memory(self):
        from sillo.events.transports.memory import MemoryTransport

        assert isinstance(EventEmitter().transport, MemoryTransport)


class TestLifecycle:
    async def test_start_starts_the_transport(self, emitter, transport):
        await emitter.start()
        assert transport.started is True

    async def test_stop_stops_the_transport(self, emitter, transport):
        await emitter.start()
        await emitter.stop()
        assert transport.stopped is True

    async def test_start_subscribes_events_registered_beforehand(
        self, emitter, transport
    ):
        @emitter.on("orders.created")
        def listener():
            return None

        await emitter.start()

        assert "orders.created" in transport.subscribed

    async def test_registering_after_start_subscribes_immediately(
        self, emitter, transport
    ):
        await emitter.start()

        @emitter.on("orders.shipped")
        def listener():
            return None

        # The subscription is scheduled on the running loop.
        await asyncio.sleep(0.05)

        assert "orders.shipped" in transport.subscribed

    async def test_restarting_resubscribes_every_registered_event(
        self, emitter, transport
    ):
        # start() iterates pending subscriptions *and* everything already
        # registered, so a second start() asks again. That is safe because a
        # transport's subscribe is idempotent — RedisTransport keeps its own
        # _subscribed set — but it does mean the call is repeated.
        @emitter.on("orders.created")
        def listener():
            return None

        await emitter.start()
        await emitter.start()

        assert transport.subscribed.count("orders.created") == 2

    async def test_the_pending_set_is_cleared_after_start(self, emitter):
        @emitter.on("orders.created")
        def listener():
            return None

        await emitter.start()

        assert emitter._pending_subscriptions == set()


class TestDispatch:
    async def test_an_envelope_reaches_the_listener(self, emitter):
        seen = []

        @emitter.on("orders.created")
        def listener(*args, **kwargs):
            seen.append((args, kwargs))

        await emitter._dispatch(
            "orders.created", {"args": [1, 2], "kwargs": {"k": "v"}}
        )

        assert seen == [((1, 2), {"k": "v"})]

    async def test_an_envelope_for_an_unknown_channel_is_ignored(self, emitter):
        await emitter._dispatch("nobody.listening", {"args": [], "kwargs": {}})

    async def test_an_envelope_without_args_still_dispatches(self, emitter):
        called = []

        @emitter.on("ping")
        def listener():
            called.append(True)

        await emitter._dispatch("ping", {})

        assert called == [True]


class TestDefaultErrorHandler:
    async def test_it_logs_rather_than_raising(self, emitter, caplog):
        await emitter._default_error_handler(
            RuntimeError("listener blew up"), "orders", {}
        )

    async def test_it_reports_the_channel(self, emitter, caplog):
        import logging

        with caplog.at_level(logging.ERROR, logger="sillo.events"):
            await emitter._default_error_handler(
                RuntimeError("boom"), "orders.created", {}
            )

        assert "orders.created" in caplog.text


class TestEventAccess:
    def test_contains_reports_registration(self, emitter):
        assert "orders" not in emitter

        emitter.event("orders")

        assert "orders" in emitter

    def test_getitem_returns_the_event(self, emitter):
        assert emitter["orders"] is emitter.event("orders")

    def test_event_names_lists_them(self, emitter):
        emitter.event("a")
        emitter.event("b")

        assert set(emitter.event_names()) == {"a", "b"}

    def test_has_event_matches_contains(self, emitter):
        emitter.event("a")

        assert emitter.has_event("a") is True
        assert emitter.has_event("b") is False

    def test_remove_event_drops_it(self, emitter):
        emitter.event("a")

        emitter.remove_event("a")

        assert "a" not in emitter

    def test_remove_all_events_empties_the_registry(self, emitter):
        emitter.event("a")
        emitter.event("b")

        emitter.remove_all_events()

        assert emitter.event_names() == []


class TestListeners:
    def test_once_fires_a_single_time(self, emitter):
        calls = []

        @emitter.once("ping")
        def listener():
            calls.append(1)

        emitter.emit_sync("ping")
        emitter.emit_sync("ping")

        assert calls == [1]

    def test_remove_listener_detaches_it(self, emitter):
        calls = []

        def listener():
            calls.append(1)

        emitter.on("ping")(listener)
        emitter.remove_listener("ping", listener)
        emitter.emit_sync("ping")

        assert calls == []

    def test_remove_all_listeners_for_one_event(self, emitter):
        calls = []

        @emitter.on("ping")
        def listener():
            calls.append(1)

        emitter.remove_all_listeners("ping")
        emitter.emit_sync("ping")

        assert calls == []

    def test_remove_all_listeners_everywhere(self, emitter):
        calls = []

        @emitter.on("a")
        def one():
            calls.append("a")

        @emitter.on("b")
        def two():
            calls.append("b")

        emitter.remove_all_listeners()
        emitter.emit_sync("a")
        emitter.emit_sync("b")

        assert calls == []


class TestNamespaces:
    def test_namespace_returns_a_namespace(self, emitter):
        assert isinstance(emitter.namespace("orders"), EventNamespace)

    def test_a_namespaced_event_is_prefixed(self, emitter):
        orders = emitter.namespace("orders")

        orders.event("created")

        assert "orders:created" in emitter

    def test_getitem_on_a_namespace_prefixes_too(self, emitter):
        orders = emitter.namespace("orders")

        orders["created"]

        assert "orders:created" in emitter

    def test_namespaces_nest(self, emitter):
        emitter.namespace("a").namespace("b").event("c")

        assert "a:b:c" in emitter

    def test_on_registers_against_the_prefixed_name(self, emitter):
        orders = emitter.namespace("orders")
        calls = []

        @orders.on("created")
        def listener():
            calls.append(1)

        emitter.emit_sync("orders:created")

        assert calls == [1]

    def test_on_can_be_called_directly_rather_than_as_a_decorator(self, emitter):
        orders = emitter.namespace("orders")
        calls = []

        def listener():
            calls.append(1)

        orders.on("created", listener)
        emitter.emit_sync("orders:created")

        assert calls == [1]

    def test_once_on_a_namespace_fires_a_single_time(self, emitter):
        orders = emitter.namespace("orders")
        calls = []

        @orders.once("created")
        def listener():
            calls.append(1)

        emitter.emit_sync("orders:created")
        emitter.emit_sync("orders:created")

        assert calls == [1]

    def test_once_can_be_called_directly_too(self, emitter):
        orders = emitter.namespace("orders")
        calls = []

        def listener():
            calls.append(1)

        orders.once("created", listener)
        emitter.emit_sync("orders:created")
        emitter.emit_sync("orders:created")

        assert calls == [1]


class TestDeprecatedAsyncEmitter:
    """``AsyncEventEmitter`` predates native async listeners and is deprecated."""

    def test_constructing_it_warns(self):
        from sillo.events.emitter import AsyncEventEmitter

        with pytest.warns(DeprecationWarning, match="AsyncEventEmitter"):
            emitter = AsyncEventEmitter()

        emitter.shutdown()

    async def test_emit_async_runs_the_listener(self):
        from sillo.events.emitter import AsyncEventEmitter

        with pytest.warns(DeprecationWarning):
            emitter = AsyncEventEmitter()

        calls = []

        @emitter.on("ping")
        def listener():
            calls.append(1)

        try:
            await emitter.emit_async("ping")
        finally:
            emitter.shutdown()

        assert calls == [1]

    async def test_schedule_emit_returns_an_awaitable(self):
        from sillo.events.emitter import AsyncEventEmitter

        with pytest.warns(DeprecationWarning):
            emitter = AsyncEventEmitter()

        calls = []

        @emitter.on("ping")
        def listener():
            calls.append(1)

        try:
            await emitter.schedule_emit("ping")
        finally:
            emitter.shutdown()

        assert calls == [1]
