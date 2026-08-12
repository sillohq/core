"""``RecordTransport`` — events persisted as database rows.

Every emitted event becomes an ``EventMessage`` row that tracks its own
delivery, so the transport doubles as an audit log and a crash-recovery
mechanism through ``replay()``. It needed a configured Tortoise database, so
none of it ran: the module sat at 26%.
"""

import inspect

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.events.transports.base import TransportError, serialize_envelope
from sillo.events.transports.record import RecordTransport, build_event_message

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)

EventMessage = build_event_message()


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_events.test_record_transport"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


@pytest.fixture
def transport():
    return RecordTransport(namespace="test", model=EventMessage)


def collector():
    seen = []

    async def dispatch(channel, envelope):
        seen.append((channel, envelope))

    return seen, dispatch


class TestModelResolution:
    def test_an_explicit_model_is_used(self, transport):
        assert transport.model is EventMessage

    def test_a_missing_model_reports_the_setup_step(self):
        import sillo.events.transports.record as record_module

        original = record_module.EventMessage
        record_module.EventMessage = None
        try:
            with pytest.raises(TransportError, match="setup_event_record"):
                RecordTransport().model
        finally:
            record_module.EventMessage = original

    def test_the_built_model_has_the_documented_columns(self):
        for column in ("channel", "payload", "status", "attempts"):
            assert column in EventMessage._meta.fields


class TestLifecycle:
    async def test_start_marks_it_running(self, transport):
        await transport.start()
        assert transport.running is True

    async def test_stop_marks_it_not_running(self, transport):
        await transport.start()
        await transport.stop()
        assert transport.running is False


class TestPublishing:
    async def test_an_event_is_persisted_and_delivered(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)

        await transport.publish("orders", {"event": "created"})

        row = await EventMessage.get(channel="test:orders")
        assert row.status == "delivered"
        assert seen[0][0] == "orders"

    async def test_the_channel_is_stored_namespaced(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)

        await transport.publish("orders", {"event": "x"})

        assert await EventMessage.filter(channel="test:orders").exists()

    async def test_a_failing_listener_marks_the_row_failed(self, transport):
        async def exploding(channel, envelope):
            raise RuntimeError("listener blew up")

        transport._deliver = exploding

        await transport.publish("orders", {"event": "x"})

        row = await EventMessage.get(channel="test:orders")
        assert row.status == "failed"
        assert row.attempts == 1

    async def test_every_event_gets_its_own_row(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)

        await transport.publish("orders", {"event": "one"})
        await transport.publish("orders", {"event": "two"})

        assert await EventMessage.filter(channel="test:orders").count() == 2


class TestReplay:
    async def test_pending_rows_are_redelivered(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        await EventMessage.create(
            channel="test:orders",
            payload=serialize_envelope({"event": "recovered"}),
            status="pending",
        )

        replayed = await transport.replay()

        assert replayed == 1
        assert seen[0][1]["event"] == "recovered"

    async def test_a_replayed_row_becomes_delivered(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        row = await EventMessage.create(
            channel="test:orders",
            payload=serialize_envelope({"event": "x"}),
            status="failed",
        )

        await transport.replay()

        assert (await EventMessage.get(id=row.id)).status == "delivered"

    async def test_the_namespace_is_stripped_before_dispatch(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        await EventMessage.create(
            channel="test:orders",
            payload=serialize_envelope({"event": "x"}),
            status="pending",
        )

        await transport.replay()

        assert seen[0][0] == "orders"

    async def test_delivered_rows_are_left_alone(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        await EventMessage.create(
            channel="test:orders",
            payload=serialize_envelope({"event": "x"}),
            status="delivered",
        )

        assert await transport.replay() == 0
        assert seen == []

    async def test_statuses_can_be_selected(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        await EventMessage.create(
            channel="test:a", payload=serialize_envelope({"e": 1}), status="pending"
        )
        await EventMessage.create(
            channel="test:b", payload=serialize_envelope({"e": 2}), status="failed"
        )

        assert await transport.replay(statuses=("failed",)) == 1

    async def test_the_limit_bounds_the_batch(self, transport):
        seen, dispatch = collector()
        transport.bind(dispatch)
        for i in range(5):
            await EventMessage.create(
                channel="test:orders",
                payload=serialize_envelope({"i": i}),
                status="pending",
            )

        assert await transport.replay(limit=2) == 2

    async def test_a_corrupt_payload_bumps_attempts_and_is_counted_out(
        self, transport
    ):
        seen, dispatch = collector()
        transport.bind(dispatch)
        row = await EventMessage.create(
            channel="test:orders", payload="not-json-at-all", status="pending"
        )

        replayed = await transport.replay()

        assert replayed == 0
        refreshed = await EventMessage.get(id=row.id)
        assert refreshed.attempts == 1
        assert refreshed.status == "pending"

    async def test_a_failing_listener_bumps_attempts_on_replay(self, transport):
        async def exploding(channel, envelope):
            raise RuntimeError("listener blew up")

        transport._deliver = exploding
        row = await EventMessage.create(
            channel="test:orders",
            payload=serialize_envelope({"event": "x"}),
            status="pending",
        )

        assert await transport.replay() == 0
        assert (await EventMessage.get(id=row.id)).attempts == 1

    async def test_replaying_an_empty_table_returns_zero(self, transport):
        assert await transport.replay() == 0
