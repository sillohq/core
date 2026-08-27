"""Covers WebSocketTestSession helper methods and lifecycle edge cases that
the broader websocket test suite (which mostly drives sillo's own
ChannelWebSocket abstraction) doesn't reach directly: send_bytes/send_json,
receive_text/receive_bytes/receive_json, an app that ignores disconnect and
must be cancelled, and an app that raises while __exit__ is draining it.
"""

from __future__ import annotations

import anyio
import pytest

from sillo.testclient import TestClient


def _echo_app():
    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                return
            if "text" in message:
                await send({"type": "websocket.send", "text": message["text"]})
            elif "bytes" in message:
                await send({"type": "websocket.send", "bytes": message["bytes"]})

    return app


def test_send_bytes_and_receive_bytes():
    client = TestClient(_echo_app())
    with client.websocket_connect("/ws") as session:
        session.send_bytes(b"hello")
        assert session.receive_bytes() == b"hello"
        session.close()


def test_send_text_and_receive_text():
    client = TestClient(_echo_app())
    with client.websocket_connect("/ws") as session:
        session.send_text("hi")
        assert session.receive_text() == "hi"
        session.close()


@pytest.mark.parametrize("mode", ["text", "binary"])
def test_send_json_and_receive_json(mode):
    client = TestClient(_echo_app())
    with client.websocket_connect("/ws") as session:
        session.send_json({"a": 1}, mode=mode)
        assert session.receive_json(mode=mode) == {"a": 1}
        session.close()


def test_exit_cancels_app_that_ignores_disconnect():
    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        await anyio.sleep_forever()

    client = TestClient(app)
    with client.websocket_connect("/ws"):
        pass


def test_exit_reraises_exception_from_pending_queue():
    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        await receive()
        raise RuntimeError("blew up during close")

    client = TestClient(app)
    with pytest.raises(RuntimeError, match="blew up during close"):
        with client.websocket_connect("/ws"):
            pass
