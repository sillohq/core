"""
The WebSocket ASGI state machine, driven directly.

A server that speaks the protocol correctly never produces these sequences,
so they are exercised by feeding the connection object raw ASGI messages. The
point is that a misbehaving server or a double-close in application code
fails loudly instead of writing frames into a dead socket.
"""

import asyncio

import pytest

from sillo.websockets.base import WebSocket, WebSocketState


def _run(coro):
    return asyncio.run(coro)


def _socket(incoming=(), on_send=None):
    """A connection over a scripted inbox and a recording outbox."""
    queue = list(incoming)
    sent = []

    async def receive():
        return queue.pop(0) if queue else {"type": "websocket.disconnect", "code": 1005}

    async def send(message):
        if on_send is not None:
            on_send(message)
        sent.append(message)

    socket = WebSocket(
        {"type": "websocket", "path": "/ws", "headers": [], "query_string": b""},
        receive,
        send,
    )
    socket.sent = sent
    return socket


# ── receiving ────────────────────────────────────────────────────────────


def test_the_first_message_must_be_a_connect():
    socket = _socket([{"type": "websocket.receive", "text": "early"}])
    with pytest.raises(RuntimeError, match="websocket.connect"):
        _run(socket.receive())


def test_a_connect_moves_the_client_to_connected():
    socket = _socket([{"type": "websocket.connect"}])
    _run(socket.receive())
    assert socket.client_state == WebSocketState.CONNECTED


def test_an_unexpected_message_after_connect_is_refused():
    socket = _socket(
        [{"type": "websocket.connect"}, {"type": "websocket.connect"}]
    )
    _run(socket.receive())
    with pytest.raises(RuntimeError, match="websocket.receive"):
        _run(socket.receive())


def test_a_disconnect_moves_the_client_to_disconnected():
    socket = _socket(
        [{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}]
    )
    _run(socket.receive())
    _run(socket.receive())
    assert socket.client_state == WebSocketState.DISCONNECTED


def test_receiving_past_a_disconnect_is_refused():
    async def scenario():
        socket = _socket(
            [
                {"type": "websocket.connect"},
                {"type": "websocket.disconnect", "code": 1000},
            ]
        )
        await socket.receive()
        await socket.receive()
        await socket.receive()

    with pytest.raises(RuntimeError, match="disconnect"):
        _run(scenario())


# ── sending ──────────────────────────────────────────────────────────────


def test_the_first_send_must_open_or_close_the_connection():
    socket = _socket()
    with pytest.raises(RuntimeError, match="websocket.accept"):
        _run(socket.send({"type": "websocket.send", "text": "too early"}))


def test_accepting_moves_the_application_to_connected():
    socket = _socket()
    _run(socket.send({"type": "websocket.accept"}))
    assert socket.application_state == WebSocketState.CONNECTED


def test_closing_before_accepting_moves_to_disconnected():
    socket = _socket()
    _run(socket.send({"type": "websocket.close", "code": 1000}))
    assert socket.application_state == WebSocketState.DISCONNECTED


def test_an_unexpected_message_while_connected_is_refused():
    socket = _socket()
    _run(socket.send({"type": "websocket.accept"}))
    with pytest.raises(RuntimeError, match="websocket.send"):
        _run(socket.send({"type": "websocket.accept"}))


def test_sending_after_closing_is_refused():
    """Double-close in application code has to surface rather than write into
    a socket the server has already torn down."""
    socket = _socket()
    _run(socket.send({"type": "websocket.accept"}))
    _run(socket.send({"type": "websocket.close", "code": 1000}))
    with pytest.raises(RuntimeError, match="close message"):
        _run(socket.send({"type": "websocket.send", "text": "after close"}))


def test_a_broken_pipe_becomes_a_disconnect():
    """The transport is already gone; the caller should see a disconnect, not
    a raw OSError from the socket layer."""
    from sillo.websockets.base import WebSocketDisconnect

    def explode(message):
        if message["type"] == "websocket.send":
            raise OSError("broken pipe")

    socket = _socket(on_send=explode)
    _run(socket.send({"type": "websocket.accept"}))
    with pytest.raises(WebSocketDisconnect) as info:
        _run(socket.send({"type": "websocket.send", "text": "into the void"}))
    assert info.value.code == 1006
    assert socket.application_state == WebSocketState.DISCONNECTED


# ── the denial-response path ─────────────────────────────────────────────


def test_starting_a_denial_response_enters_the_response_state():
    """Rejecting a handshake with an HTTP response is a distinct state; normal
    frame sends are not valid in it."""
    socket = _socket()
    _run(
        socket.send(
            {"type": "websocket.http.response.start", "status": 403, "headers": []}
        )
    )
    assert socket.application_state == WebSocketState.RESPONSE


def test_the_denial_body_must_follow_the_start():
    socket = _socket()
    _run(
        socket.send(
            {"type": "websocket.http.response.start", "status": 403, "headers": []}
        )
    )
    with pytest.raises(RuntimeError, match="websocket.http.response.body"):
        _run(socket.send({"type": "websocket.send", "text": "wrong message"}))


def test_a_complete_denial_response_ends_the_connection():
    socket = _socket()
    _run(
        socket.send(
            {"type": "websocket.http.response.start", "status": 403, "headers": []}
        )
    )
    _run(socket.send({"type": "websocket.http.response.body", "body": b"denied"}))
    assert socket.application_state == WebSocketState.DISCONNECTED


def test_a_streamed_denial_body_stays_open_until_the_last_chunk():
    socket = _socket()
    _run(
        socket.send(
            {"type": "websocket.http.response.start", "status": 403, "headers": []}
        )
    )
    _run(
        socket.send(
            {"type": "websocket.http.response.body", "body": b"de", "more_body": True}
        )
    )
    assert socket.application_state == WebSocketState.RESPONSE
    _run(socket.send({"type": "websocket.http.response.body", "body": b"nied"}))
    assert socket.application_state == WebSocketState.DISCONNECTED


# ── initial state ────────────────────────────────────────────────────────


def test_a_new_connection_starts_in_connecting():
    socket = _socket()
    assert socket.client_state == WebSocketState.CONNECTING
    assert socket.application_state == WebSocketState.CONNECTING


def test_a_non_websocket_scope_is_rejected():
    async def receive():
        return {}

    async def send(message):
        return None

    with pytest.raises(AssertionError):
        WebSocket({"type": "http", "headers": [], "query_string": b""}, receive, send)
