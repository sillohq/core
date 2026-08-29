"""
``WebSocketConsumer`` message decoding and group helpers.

The ``encoding`` attribute decides how each frame is turned into ``data``.
Getting the wrong frame kind is a protocol error, so the consumer closes with
1003 (unsupported data) rather than handing the endpoint something it cannot
use — those close paths are the bulk of what is checked here.
"""

import asyncio
import uuid
from typing import Callable

import pytest

from sillo import SilloApp
from sillo.testclient import TestClient
from sillo.websockets import Channel, ChannelBox, WebSocketContext, WebSocketConsumer
from sillo.websockets import status
from sillo.websockets.utils import PayloadTypeEnum


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_channel_box():
    _run(ChannelBox.flush_groups())
    _run(ChannelBox.flush_history())
    yield
    _run(ChannelBox.flush_groups())
    _run(ChannelBox.flush_history())


def _app_with(consumer_cls, path="/ws"):
    app = SilloApp()
    app.router.routes.append(consumer_cls.as_route(path))
    return app


# ── text encoding ────────────────────────────────────────────────────────


def test_a_text_consumer_receives_text(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        encoding = "text"

        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hello")
            ws.close()

    assert received == ["hello"]


def test_a_text_consumer_rejects_a_binary_frame(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Echo(WebSocketConsumer):
        encoding = "text"

    with test_client_factory(_app_with(Echo), raise_server_exceptions=False) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"binary")
            message = ws.receive()

    assert message["type"] == "websocket.close"
    assert message["code"] == status.WS_1003_UNSUPPORTED_DATA


# ── bytes encoding ───────────────────────────────────────────────────────


def test_a_bytes_consumer_receives_bytes(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        encoding = "bytes"

        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"payload")
            ws.close()

    assert received == [b"payload"]


def test_a_bytes_consumer_rejects_a_text_frame(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Echo(WebSocketConsumer):
        encoding = "bytes"

    with test_client_factory(_app_with(Echo), raise_server_exceptions=False) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("text")
            message = ws.receive()

    assert message["code"] == status.WS_1003_UNSUPPORTED_DATA


# ── json encoding ────────────────────────────────────────────────────────


def test_a_json_consumer_parses_text_frames(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        encoding = "json"

        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text('{"n": 1}')
            ws.close()

    assert received == [{"n": 1}]


def test_a_json_consumer_parses_binary_frames(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        encoding = "json"

        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b'{"n": 2}')
            ws.close()

    assert received == [{"n": 2}]


def test_malformed_json_closes_the_connection(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Echo(WebSocketConsumer):
        encoding = "json"

    with test_client_factory(_app_with(Echo), raise_server_exceptions=False) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("{not json")
            message = ws.receive()

    assert message["code"] == status.WS_1003_UNSUPPORTED_DATA


# ── no declared encoding ─────────────────────────────────────────────────


def test_an_unencoded_consumer_passes_text_through(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("raw")
            ws.close()

    assert received == ["raw"]


def test_an_unencoded_consumer_passes_bytes_through(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"raw")
            ws.close()

    assert received == [b"raw"]


# ── lifecycle hooks ──────────────────────────────────────────────────────


def test_the_connect_hook_runs(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    events = []

    class Tracked(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            events.append("connect")
            await websocket.accept()

    with test_client_factory(_app_with(Tracked)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert events == ["connect"]


def test_the_disconnect_hook_receives_the_close_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    codes = []

    class Tracked(WebSocketConsumer):
        encoding = "text"

        async def on_disconnect(self, websocket, close_code):
            codes.append(close_code)

    with test_client_factory(_app_with(Tracked)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.close(code=4004)

    assert codes == [4004]


def test_the_disconnect_hook_runs_even_after_a_failure(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Cleanup belongs in ``on_disconnect``, so it has to run when the handler
    blows up as well as when the client leaves politely."""
    codes = []

    class Broken(WebSocketConsumer):
        encoding = "text"

        async def on_receive(self, websocket, data):
            raise RuntimeError("handler exploded")

        async def on_disconnect(self, websocket, close_code):
            codes.append(close_code)

    with test_client_factory(_app_with(Broken), raise_server_exceptions=False) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("boom")

    assert codes == [status.WS_1011_INTERNAL_ERROR]


def test_several_messages_reach_the_handler(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    received = []

    class Echo(WebSocketConsumer):
        encoding = "text"

        async def on_receive(self, websocket, data):
            received.append(data)

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("one")
            ws.send_text("two")
            ws.send_text("three")
            ws.close()

    assert received == ["one", "two", "three"]


def test_a_consumer_can_reply(test_client_factory: Callable[[SilloApp], TestClient]):
    class Echo(WebSocketConsumer):
        encoding = "text"

        async def on_receive(self, websocket, data):
            await websocket.send_text(f"echo: {data}")

    with test_client_factory(_app_with(Echo)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hi")
            assert ws.receive_text() == "echo: hi"


# ── channel and group helpers ────────────────────────────────────────────


def test_a_json_consumer_builds_a_json_channel(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    class Tracked(WebSocketConsumer):
        encoding = "json"

        async def on_connect(self, websocket):
            await websocket.accept()
            seen.append(self.channel.payload_type)

    with test_client_factory(_app_with(Tracked)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert seen == [PayloadTypeEnum.JSON.value]


def test_a_text_consumer_builds_a_text_channel(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    class Tracked(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            seen.append(self.channel.payload_type)

    with test_client_factory(_app_with(Tracked)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert seen == [PayloadTypeEnum.TEXT.value]


def test_joining_a_group_registers_the_channel(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    sizes = []

    class Joiner(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            await self.join_group("room")
            sizes.append(len(await self.group("room")))

    with test_client_factory(_app_with(Joiner)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert sizes == [1]


def test_leaving_a_group_deregisters_the_channel(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    sizes = []

    class Joiner(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            await self.join_group("room")
            await self.leave_group("room")
            sizes.append(len(await self.group("room")))

    with test_client_factory(_app_with(Joiner)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert sizes == [0]


def test_a_consumer_can_broadcast_to_its_group(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Broadcaster(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            await self.join_group("room")

        async def on_receive(self, websocket, data):
            await self.broadcast(data, group_name="room")

    with test_client_factory(_app_with(Broadcaster)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("to everyone")
            assert ws.receive_text() == "to everyone"


def test_a_broadcast_can_be_recorded_in_history(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Broadcaster(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            await self.join_group("room")

        async def on_receive(self, websocket, data):
            await self.broadcast(data, group_name="room", save_history=True)

    with test_client_factory(_app_with(Broadcaster)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("remembered")
            ws.receive_text()

    assert len(_run(ChannelBox.show_history("room"))) == 1


def test_a_message_can_be_addressed_to_one_channel(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Direct(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            await self.join_group("room")

        async def on_receive(self, websocket, data):
            await self.send_to(self.channel.uuid, data)

    with test_client_factory(_app_with(Direct)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("just for you")
            assert ws.receive_text() == "just for you"


def test_addressing_an_unknown_channel_is_survivable(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A stale channel id must not take the connection down."""
    finished = []

    class Direct(WebSocketConsumer):
        encoding = "text"

        async def on_receive(self, websocket, data):
            await self.send_to(uuid.uuid4(), data)
            finished.append(True)

    with test_client_factory(_app_with(Direct)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("nowhere")
            ws.close()

    assert finished == [True]


def test_the_group_helper_reports_an_unknown_group_as_empty(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    sizes = []

    class Inspector(WebSocketConsumer):
        encoding = "text"

        async def on_connect(self, websocket):
            await websocket.accept()
            sizes.append(len(await self.group("no-such-room")))

    with test_client_factory(_app_with(Inspector)) as client:
        with client.websocket_connect("/ws"):
            pass

    assert sizes == [0]


# ── construction ─────────────────────────────────────────────────────────


def test_logging_is_on_by_default():
    assert WebSocketConsumer().logging_enabled is True


def test_logging_can_be_switched_off():
    assert WebSocketConsumer(logging_enabled=False).logging_enabled is False


def test_a_custom_logger_is_kept():
    import logging as stdlib_logging

    logger = stdlib_logging.getLogger("my-app")
    assert WebSocketConsumer(logger=logger).logger is logger


def test_as_route_builds_a_websocket_route():
    from sillo.core.routing.websocket import WebsocketRoute

    class Echo(WebSocketConsumer):
        encoding = "text"

    assert isinstance(Echo.as_route("/ws"), WebsocketRoute)
