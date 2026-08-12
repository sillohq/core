"""The transport factory and the pieces of ``BaseTransport`` shared by all of them.

``get_transport`` is the seam every backend is selected through, and the
envelope helpers below it decide what survives serialisation. Neither was
exercised beyond the memory backend.
"""

import pytest

from sillo.events.transports import (
    _AVAILABLE,
    get_transport,
    register_transport,
    setup_event_record,
)
from sillo.events.transports.base import (
    BaseTransport,
    deserialize_envelope,
    serialize_payload,
    serialize_envelope,
)
from sillo.events.transports.memory import MemoryTransport
from sillo.events.transports.persistent import PersistentTransport
from sillo.events.transports.record import RecordTransport
from sillo.events.transports.redis import RedisTransport


class ConcreteTransport(BaseTransport):
    """BaseTransport declares publish abstract, so tests need a body for it."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.published = []

    async def publish(self, channel, envelope):
        self.published.append((channel, envelope))


class TestGetTransport:
    def test_memory_is_the_default(self):
        assert isinstance(get_transport(), MemoryTransport)

    @pytest.mark.parametrize(
        "backend,expected",
        [
            ("memory", MemoryTransport),
            ("redis", RedisTransport),
            ("persistent", PersistentTransport),
            ("record", RecordTransport),
        ],
    )
    def test_each_named_backend_resolves_to_its_class(self, backend, expected):
        assert isinstance(get_transport(backend), expected)

    def test_the_namespace_is_forwarded(self):
        assert get_transport("memory", namespace="app").namespace == "app"

    def test_extra_kwargs_reach_the_backend(self):
        transport = get_transport("redis", url="redis://example:6379/2")
        assert transport._url == "redis://example:6379/2"

    def test_an_unknown_backend_is_refused(self):
        with pytest.raises((ValueError, KeyError, ImportError)):
            get_transport("no-such-backend")


class TestRegisterTransport:
    def test_a_registered_backend_becomes_resolvable(self):
        register_transport(
            "fake-test-backend", "sillo.events.transports.memory:MemoryTransport"
        )
        try:
            assert isinstance(get_transport("fake-test-backend"), MemoryTransport)
        finally:
            _AVAILABLE.pop("fake-test-backend", None)

    def test_registration_records_the_dotted_path(self):
        register_transport("another-test-backend", "some.module:Thing")
        try:
            assert _AVAILABLE["another-test-backend"] == "some.module:Thing"
        finally:
            _AVAILABLE.pop("another-test-backend", None)

    def test_a_registered_path_that_cannot_import_fails_when_requested(self):
        register_transport("broken-test-backend", "no.such.module:Nope")
        try:
            with pytest.raises((ImportError, ModuleNotFoundError)):
                get_transport("broken-test-backend")
        finally:
            _AVAILABLE.pop("broken-test-backend", None)


class TestSetupEventRecord:
    def test_it_returns_the_event_message_model(self):
        assert setup_event_record().__name__ == "EventMessage"


class TestEnvelopes:
    def test_an_envelope_carries_an_event_id(self):
        assert "event_id" in serialize_payload((1,), {"a": 2})

    def test_two_envelopes_get_different_ids(self):
        assert (
            serialize_payload((), {})["event_id"]
            != serialize_payload((), {})["event_id"]
        )

    def test_args_and_kwargs_are_both_carried(self):
        envelope = serialize_payload((1, "two"), {"three": 3})

        assert envelope["args"] == [1, "two"]
        assert envelope["kwargs"] == {"three": 3}

    def test_it_is_stamped_with_a_timestamp(self):
        assert serialize_payload((), {})["ts"] > 0

    def test_a_payload_round_trips_through_serialisation(self):
        envelope = serialize_payload((1,), {"nested": {"b": [1, 2]}})

        restored = deserialize_envelope(serialize_envelope(envelope))

        assert restored["args"] == envelope["args"]
        assert restored["kwargs"] == envelope["kwargs"]

    def test_an_unserialisable_value_is_replaced_rather_than_raising(self):
        class Hostile:
            def __repr__(self):
                return "<hostile>"

        envelope = serialize_payload((), {"bad": Hostile()})

        assert envelope["kwargs"]["bad"] == {"__unsupported__": "<hostile>"}
        # And the whole envelope still serialises.
        assert "__unsupported__" in serialize_envelope(envelope)

    def test_an_unserialisable_positional_is_replaced_too(self):
        class Hostile:
            def __repr__(self):
                return "<hostile-arg>"

        envelope = serialize_payload((Hostile(),), {})

        assert envelope["args"][0] == {"__unsupported__": "<hostile-arg>"}

    def test_deserialising_junk_raises(self):
        with pytest.raises(Exception):
            deserialize_envelope("not-json-at-all")


class TestBaseTransportLifecycle:
    async def test_start_and_stop_toggle_running(self):
        transport = ConcreteTransport()

        assert transport.running is False
        await transport.start()
        assert transport.running is True
        await transport.stop()
        assert transport.running is False

    def test_the_namespace_prefixes_a_channel(self):
        assert ConcreteTransport(namespace="app")._channel("orders") == "app:orders"

    def test_no_namespace_leaves_the_channel_bare(self):
        assert ConcreteTransport()._channel("orders") == "orders"

    def test_binding_replaces_the_dispatch_callback(self):
        transport = ConcreteTransport()

        async def dispatch(channel, envelope):
            return None

        transport.bind(dispatch)

        assert transport._dispatch is dispatch

    def test_an_error_handler_can_be_set(self):
        transport = ConcreteTransport()

        async def on_error(exc, channel, envelope):
            return None

        transport.set_error_handler(on_error)

        assert transport._on_error is on_error


class TestBaseTransportDelivery:
    async def test_delivery_without_a_dispatch_callback_is_a_no_op(self):
        await ConcreteTransport()._deliver("orders", {"event": "x"})

    async def test_a_duplicate_event_id_is_dropped(self):
        transport = ConcreteTransport()
        seen = []

        async def dispatch(channel, envelope):
            seen.append(envelope)

        transport.bind(dispatch)
        envelope = {"event_id": "same", "event": "x"}

        await transport._deliver("orders", envelope)
        await transport._deliver("orders", envelope)

        assert len(seen) == 1

    async def test_a_listener_error_is_routed_to_on_error(self):
        transport = ConcreteTransport()
        errors = []

        async def dispatch(channel, envelope):
            raise RuntimeError("listener blew up")

        async def on_error(exc, channel, envelope):
            errors.append((exc, channel))

        transport.bind(dispatch)
        transport.set_error_handler(on_error)

        await transport._deliver("orders", {"event": "x"})

        assert len(errors) == 1
        assert errors[0][1] == "orders"

    async def test_a_raising_error_handler_does_not_escape(self):
        transport = ConcreteTransport()

        async def dispatch(channel, envelope):
            raise RuntimeError("listener blew up")

        async def on_error(exc, channel, envelope):
            raise RuntimeError("the handler is broken too")

        transport.bind(dispatch)
        transport.set_error_handler(on_error)

        # Neither failure may reach the caller.
        await transport._deliver("orders", {"event": "x"})

    async def test_the_seen_set_is_bounded(self):
        transport = ConcreteTransport()
        transport._seen_max = 4
        seen = []

        async def dispatch(channel, envelope):
            seen.append(envelope)

        transport.bind(dispatch)

        for i in range(10):
            await transport._deliver("orders", {"event_id": f"e{i}"})

        assert len(transport._seen) <= 10
        assert len(seen) == 10
