"""
WebSocket protocol handling: binary mode, iteration, close codes, and the
state machine that rejects out-of-order ASGI messages.

The state assertions matter because an ASGI server is entitled to hang up at
any moment; the connection object has to notice and refuse to keep talking
rather than emit frames into a closed socket.
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo.testclient import TestClient
from sillo.websockets import WebSocketContext, WebSocketDisconnect


# ── binary and json modes ────────────────────────────────────────────────


def test_binary_json_is_sent_and_received(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        payload = await websocket.receive_json(mode="binary")
        await websocket.send_json({"echo": payload}, mode="binary")
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"a": 1}, mode="binary")
            assert ws.receive_json(mode="binary") == {"echo": {"a": 1}}


def test_an_unknown_receive_mode_is_rejected(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        try:
            await websocket.receive_json(mode="morse")
        except RuntimeError as exc:
            seen.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("{}")

    assert seen and "mode" in seen[0]


def test_an_unknown_send_mode_is_rejected(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        try:
            await websocket.send_json({"a": 1}, mode="morse")
        except RuntimeError as exc:
            seen.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws"):
            pass

    assert seen and "mode" in seen[0]


def test_bytes_round_trip(test_client_factory: Callable[[SilloApp], TestClient]):
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        data = await websocket.receive_bytes()
        await websocket.send_bytes(data[::-1])
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"abc")
            assert ws.receive_bytes() == b"cba"


# ── iteration helpers ────────────────────────────────────────────────────


def test_iterating_text_messages(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    received = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        async for message in websocket.iter_text():
            received.append(message)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("one")
            ws.send_text("two")
            ws.close()

    assert received == ["one", "two"]


def test_iteration_ends_on_disconnect(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The loop must terminate when the client hangs up rather than raise
    out of the handler."""
    app = SilloApp()
    finished = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        async for _ in websocket.iter_text():
            pass
        finished.append(True)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("one")
            ws.close()

    assert finished == [True]


def test_iterating_bytes_messages(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    received = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        async for chunk in websocket.iter_bytes():
            received.append(chunk)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"one")
            ws.send_bytes(b"two")
            ws.close()

    assert received == [b"one", b"two"]


def test_iterating_json_messages(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    received = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        async for payload in websocket.iter_json():
            received.append(payload)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"n": 1})
            ws.send_json({"n": 2})
            ws.close()

    assert received == [{"n": 1}, {"n": 2}]


# ── connection state ─────────────────────────────────────────────────────


def test_a_socket_reports_itself_connected(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    states = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        # ``is_connected`` is a method, not a property — reading it without
        # calling it yields a bound method, which is always truthy.
        states.append(websocket.is_connected())
        await websocket.accept()
        states.append(websocket.is_connected())
        await websocket.close()
        states.append(websocket.is_connected())

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws"):
            pass

    assert states == [False, True, False]


def test_receiving_after_a_disconnect_is_refused(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    errors = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        # The low-level ``receive`` hands back the disconnect message rather
        # than raising; only the typed helpers turn it into an exception.
        message = await websocket.receive()
        errors.append(message["type"])
        try:
            await websocket.receive()
        except RuntimeError as exc:
            errors.append(str(exc))

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.close()

    assert errors[0] == "websocket.disconnect"
    assert "disconnect" in errors[1]


def test_receiving_text_from_a_closed_socket_raises_disconnect(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    disconnected = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        try:
            await websocket.receive_text()
        except WebSocketDisconnect as exc:
            disconnected.append(exc.code)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.close()

    assert disconnected


def test_receiving_text_when_the_frame_is_binary_is_an_error(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The typed helpers index the frame directly, so asking for the wrong
    kind surfaces as a ``KeyError`` on the missing field."""
    app = SilloApp()
    errors = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        try:
            await websocket.receive_text()
        except KeyError as exc:
            errors.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"binary")

    assert errors == ["'text'"]


def test_receiving_bytes_when_the_frame_is_text_is_an_error(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    errors = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        try:
            await websocket.receive_bytes()
        except KeyError as exc:
            errors.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("text")

    assert errors == ["'bytes'"]


def test_receiving_before_accepting_is_refused(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    errors = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        try:
            await websocket.receive_text()
        except RuntimeError as exc:
            errors.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws"):
                pass

    assert errors and "accept" in errors[0]


def test_sending_before_accepting_is_refused(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    errors = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        try:
            await websocket.send_text("too early")
        except RuntimeError as exc:
            errors.append(str(exc))
        await websocket.close()

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws"):
                pass

    assert errors


# ── closing ──────────────────────────────────────────────────────────────


def test_a_custom_close_code_reaches_the_client(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        await websocket.close(code=4001, reason="policy violation")

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
    assert info.value.code == 4001


def test_the_close_reason_reaches_the_client(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        await websocket.close(code=4002, reason="too chatty")

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
    assert info.value.reason == "too chatty"


def test_a_connection_can_be_refused_before_accepting(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Rejecting without accepting is how auth failures are signalled."""
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.close(code=4003)

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with client.websocket_connect("/ws"):
                pass
    assert info.value.code == 4003


def test_the_default_close_code_is_normal(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        await websocket.accept()
        await websocket.close()

    with test_client_factory(app) as client:
        with pytest.raises(WebSocketDisconnect) as info:
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
    assert info.value.code == 1000


# ── request information ──────────────────────────────────────────────────


def test_the_path_is_available(test_client_factory: Callable[[SilloApp], TestClient]):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws/room")
    async def endpoint(websocket: WebSocketContext):
        seen.append(websocket.url.path)
        await websocket.accept()
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/room"):
            pass

    assert seen == ["/ws/room"]


def test_query_parameters_are_available(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        seen.append(websocket.query_params.get("token"))
        await websocket.accept()
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws?token=abc123"):
            pass

    assert seen == ["abc123"]


def test_headers_are_available(test_client_factory: Callable[[SilloApp], TestClient]):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws")
    async def endpoint(websocket: WebSocketContext):
        seen.append(websocket.headers.get("x-client"))
        await websocket.accept()
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws", headers={"x-client": "test-suite"}):
            pass

    assert seen == ["test-suite"]


def test_path_parameters_are_available(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    app = SilloApp()
    seen = []

    @app.ws_route("/ws/{room_id}")
    async def endpoint(websocket: WebSocketContext, room_id: str):
        # Path parameters bind as keyword arguments after the context, exactly
        # as on an HTTP route, and are still on the context as well.
        assert room_id == websocket.path_params["room_id"]
        seen.append(room_id)
        await websocket.accept()
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/lobby"):
            pass

    assert seen == ["lobby"]
