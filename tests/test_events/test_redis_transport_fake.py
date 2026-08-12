"""``RedisTransport`` driven against ``fakeredis``.

The transport connects lazily and caches the client on ``_client``, so the
fake is placed there and every method under test is the real one. This class
was 16% covered because it could only run with a Redis server present — and
the deadlock fixed in 0.0.1a15 (``subscribe`` after ``start`` waiting on a
connection the listener loop never released) lived in exactly that gap.
"""

import asyncio

import pytest

from sillo.events.transports.redis import RedisTransport

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis  # noqa: E402


@pytest.fixture
def transport():
    t = RedisTransport(namespace="test")
    t._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield t


async def _stop(transport):
    """Stop without leaving the listener task pending."""
    await transport.stop()
    await asyncio.sleep(0)


class TestConnection:
    async def test_ping_succeeds_against_a_live_server(self, transport):
        assert await transport.ping() is True

    async def test_ping_reports_false_rather_than_raising(self, transport):
        class Dead:
            async def ping(self):
                raise ConnectionError("refused")

        transport._client = Dead()

        assert await transport.ping() is False

    def test_connect_reuses_the_existing_client(self, transport):
        assert transport._connect() is transport._client


class TestLifecycle:
    async def test_start_marks_it_running(self, transport):
        await transport.start()
        try:
            assert transport.running is True
        finally:
            await _stop(transport)

    async def test_start_is_idempotent(self, transport):
        await transport.start()
        first = transport._listener_task
        try:
            await transport.start()
            assert transport._listener_task is first
        finally:
            await _stop(transport)

    async def test_stop_marks_it_not_running(self, transport):
        await transport.start()
        await _stop(transport)

        assert transport.running is False

    async def test_stop_without_start_is_harmless(self, transport):
        await _stop(transport)
        assert transport.running is False


class TestSubscribing:
    async def test_subscribing_registers_the_namespaced_channel(self, transport):
        await transport.subscribe("orders")
        try:
            assert transport._channel("orders") in transport._subscribed
        finally:
            await _stop(transport)

    async def test_subscribing_starts_the_loop(self, transport):
        # A listener registered before start() must still connect.
        await transport.subscribe("orders")
        try:
            assert transport.running is True
        finally:
            await _stop(transport)

    async def test_subscribing_twice_is_idempotent(self, transport):
        await transport.subscribe("orders")
        try:
            await transport.subscribe("orders")
            assert len(transport._subscribed) == 1
        finally:
            await _stop(transport)

    async def test_subscribing_after_start_does_not_deadlock(self, transport):
        # The regression from 0.0.1a15: the listener loop held the pubsub
        # connection inside listen(), so a later subscribe waited forever on
        # a connection it would never release.
        await transport.start()
        try:
            await asyncio.wait_for(transport.subscribe("late"), timeout=2.0)
            assert transport._channel("late") in transport._subscribed
        finally:
            await _stop(transport)

    async def test_several_channels_can_be_subscribed(self, transport):
        await transport.subscribe("a")
        try:
            await transport.subscribe("b")
            assert len(transport._subscribed) == 2
        finally:
            await _stop(transport)


class TestPublishing:
    async def test_publishing_reaches_a_subscriber(self, transport):
        received = []

        def dispatch(channel, envelope):
            received.append((channel, envelope))

        transport.bind(dispatch)
        await transport.subscribe("orders")
        try:
            await transport.publish("orders", {"event": "created", "data": {"id": 1}})

            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.02)
        finally:
            await _stop(transport)

        assert received, "the listener loop never delivered the message"
        assert received[0][1]["event"] == "created"

    async def test_publishing_without_subscribers_is_harmless(self, transport):
        await transport.publish("nobody-listening", {"event": "x"})

    async def test_a_malformed_payload_is_dropped_not_raised(self, transport):
        delivered = []
        transport.bind(lambda c, e: delivered.append(e))

        await transport.subscribe("orders")
        try:
            # Bypass the transport's own serialisation to plant junk.
            await transport._client.publish(
                transport._channel("orders"), b"not-json-at-all"
            )
            await asyncio.sleep(0.1)
        finally:
            await _stop(transport)

        assert delivered == []


class TestChannelNaming:
    def test_the_namespace_prefixes_the_channel(self, transport):
        assert transport._channel("orders").startswith("test")

    def test_different_namespaces_give_different_channels(self):
        one = RedisTransport(namespace="one")
        two = RedisTransport(namespace="two")

        assert one._channel("same") != two._channel("same")

    def test_no_namespace_still_produces_a_channel(self):
        assert RedisTransport()._channel("orders")
