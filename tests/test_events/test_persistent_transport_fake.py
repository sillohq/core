"""``PersistentTransport`` — the durable, at-least-once events backlog.

Events go onto a Redis list and stay there until a worker pops and dispatches
them, so the interesting behaviour is what happens when delivery fails: the
event is requeued with an incremented attempt count, and dropped once it
exhausts ``max_retries``. None of that could run without a Redis server, so
the module sat at 22%. ``_client`` is populated lazily, which is where the
fake goes in.
"""

import asyncio

import pytest

from sillo.events.transports.persistent import PersistentTransport

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis  # noqa: E402


@pytest.fixture
def transport():
    t = PersistentTransport(namespace="test", max_retries=2)
    t._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    return t


async def drain_until(transport, predicate, timeout=2.0, then=None):
    """Run the worker until *predicate* holds, then stop it.

    *then* is awaited while the worker is still up, because ``stop()`` closes
    the Redis client and a closed one answers every command with ``None`` —
    so any assertion touching the backlog has to happen before that.
    """
    await transport.start()
    result = None
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if predicate():
                break
            await asyncio.sleep(0.02)
        if then is not None:
            result = await then()
    finally:
        await transport.stop()
        await asyncio.sleep(0)
    return result


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


class TestBacklogKey:
    def test_the_namespace_scopes_the_key(self, transport):
        assert transport._backlog_key().startswith("test")

    def test_without_a_namespace_the_bare_key_is_used(self):
        assert "backlog" in PersistentTransport()._backlog_key()

    def test_two_namespaces_do_not_collide(self):
        one = PersistentTransport(namespace="one")
        two = PersistentTransport(namespace="two")

        assert one._backlog_key() != two._backlog_key()


class TestPublishing:
    async def test_publishing_appends_to_the_backlog(self, transport):
        await transport.publish("orders", {"event": "created"})

        assert await transport._client.llen(transport._backlog_key()) == 1

    async def test_the_backlog_survives_without_a_consumer(self, transport):
        # The whole point of this transport: nothing is lost while offline.
        await transport.publish("orders", {"event": "one"})
        await transport.publish("orders", {"event": "two"})

        assert await transport._client.llen(transport._backlog_key()) == 2


class TestDraining:
    async def test_a_published_event_is_delivered(self, transport):
        received = []
        async def dispatch(channel, envelope):
            received.append(envelope)

        transport.bind(dispatch)

        await transport.publish("orders", {"event": "created"})
        await drain_until(transport, lambda: received)

        assert received
        assert received[0]["event"] == "created"

    async def test_the_channel_is_restored_on_delivery(self, transport):
        seen = []
        async def dispatch(channel, envelope):
            seen.append(channel)

        transport.bind(dispatch)

        await transport.publish("orders", {"event": "x"})
        await drain_until(transport, lambda: seen)

        assert seen == ["orders"]

    async def test_a_delivered_event_leaves_the_backlog(self, transport):
        delivered = []
        async def dispatch(channel, envelope):
            delivered.append(envelope)

        transport.bind(dispatch)
        # stop() releases the client, so hold a reference for the assertion.
        client, key = transport._client, transport._backlog_key()

        await transport.publish("orders", {"event": "x"})
        remaining = await drain_until(
            transport, lambda: delivered, then=lambda: client.llen(key)
        )

        assert delivered
        assert remaining == 0

    async def test_a_malformed_entry_is_dropped_not_retried(self, transport):
        delivered = []
        async def dispatch(channel, envelope):
            delivered.append(envelope)

        transport.bind(dispatch)

        client, key = transport._client, transport._backlog_key()
        await client.rpush(key, b"not-json")

        remaining = await drain_until(
            transport, lambda: False, timeout=0.3, then=lambda: client.llen(key)
        )

        assert delivered == []
        assert remaining == 0


class TestRetries:
    async def test_a_listener_error_does_not_trigger_a_retry(self):
        """A raising listener is swallowed, and the event is gone.

        ``BaseTransport._deliver`` catches every listener exception and routes
        it to ``on_error`` without re-raising, so the requeue branch below is
        unreachable from a listener failure. That contradicts this module's
        own docstring — "failed deliveries are requeued with a bounded retry
        count" — and means the durability this transport exists to provide
        does not cover the most likely failure. Recorded as the behaviour that
        ships, not as the behaviour that is wanted.
        """
        transport = PersistentTransport(namespace="swallowed", max_retries=5)
        transport._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        attempts = []

        async def failing(channel, envelope):
            attempts.append(envelope.get("_attempts", 0))
            raise RuntimeError("listener blew up")

        transport.bind(failing)
        client, key = transport._client, transport._backlog_key()
        await transport.publish("orders", {"event": "x"})

        remaining = await drain_until(
            transport,
            lambda: len(attempts) >= 2,
            timeout=1.5,
            then=lambda: client.llen(key),
        )

        assert len(attempts) == 1
        assert remaining == 0

    async def test_a_delivery_failure_is_requeued_with_an_attempt_count(self):
        """The requeue path itself, driven by making _deliver raise.

        This is what the retry branch was written for. Reaching it requires
        the failure to escape _deliver, which today only a transport-level
        fault does — see the test above.
        """
        transport = PersistentTransport(namespace="retry", max_retries=5)
        transport._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        attempts = []

        async def exploding_deliver(channel, envelope):
            attempts.append(envelope.get("_attempts", 0))
            raise RuntimeError("delivery infrastructure failed")

        transport._deliver = exploding_deliver
        await transport.publish("orders", {"event": "x"})
        await drain_until(transport, lambda: len(attempts) >= 2, timeout=5.0)

        # The second delivery carries a higher attempt count than the first.
        assert len(attempts) >= 2
        assert attempts[1] > attempts[0]

    async def test_an_event_is_dropped_once_retries_are_exhausted(self):
        transport = PersistentTransport(namespace="drop", max_retries=1)
        transport._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        calls = []

        async def exploding_deliver(channel, envelope):
            calls.append(1)
            raise RuntimeError("delivery infrastructure failed")

        transport._deliver = exploding_deliver
        client, key = transport._client, transport._backlog_key()
        await transport.publish("orders", {"event": "x"})

        remaining = await drain_until(
            transport,
            lambda: len(calls) >= 2,
            timeout=3.0,
            then=lambda: client.llen(key),
        )

        # Delivered, retried up to the limit, then dropped rather than looping
        # forever. max_retries=1 means at most two deliveries.
        assert calls
        assert remaining == 0


class TestLifecycle:
    async def test_start_marks_it_running(self, transport):
        await transport.start()
        try:
            assert transport.running is True
        finally:
            await transport.stop()
            await asyncio.sleep(0)

    async def test_start_is_idempotent(self, transport):
        await transport.start()
        worker = transport._worker
        try:
            await transport.start()
            assert transport._worker is worker
        finally:
            await transport.stop()
            await asyncio.sleep(0)

    async def test_stop_marks_it_not_running(self, transport):
        await transport.start()
        await transport.stop()
        await asyncio.sleep(0)

        assert transport.running is False

    async def test_stop_without_start_is_harmless(self, transport):
        await transport.stop()
        assert transport.running is False
