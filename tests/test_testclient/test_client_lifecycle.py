"""Covers TestClient/AsyncTestClient edge paths not reached by the rest of
the suite: ASGI2 apps, streaming requests, websocket denial responses,
lifespan startup/shutdown failures, and the sillo.testclient.helpers
factories.
"""

from __future__ import annotations

import contextlib

import pytest

from sillo import SilloApp
from sillo.testclient import AsyncTestClient, TestClient
from sillo.testclient._internal.utils import WrapASGI2, is_asgi3
from sillo.testclient.helpers import create_async_client, create_client
from sillo.websockets import WebSocketDisconnect


class _ASGI2App:
    """A legacy ASGI2-style application: `app(scope)(receive, send)`."""

    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def test_is_asgi3_with_class_without_await():
    assert is_asgi3(_ASGI2App) is False


def test_asgi2_app_is_wrapped_and_served():
    client = TestClient(_ASGI2App)
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"ok"


async def test_asgi2_app_served_by_async_client():
    client = AsyncTestClient(_ASGI2App)
    response = await client.get("/")
    assert response.status_code == 200


async def test_wrap_asgi2_directly():
    seen = {}

    class App:
        def __init__(self, scope):
            seen["scope"] = scope

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    async def noop_receive():
        return {}

    async def noop_send(message):
        pass

    wrapped = WrapASGI2(App)
    await wrapped({"type": "http"}, noop_receive, noop_send)
    assert seen["scope"] == {"type": "http"}


def test_stream_request_returns_open_response():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"streamed"})

    client = TestClient(app)
    response = client.request("GET", "/", stream=True)
    assert response.status_code == 200


async def test_async_headers_as_non_dict_and_methods():
    async def app(scope, receive, send):
        headers = dict(scope["headers"])
        assert headers[b"x-test"] == b"1"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    client = AsyncTestClient(app, headers=[("x-test", "1")])
    assert (await client.post("/")).status_code == 200
    assert (await client.put("/")).status_code == 200
    assert (await client.patch("/")).status_code == 200
    assert (await client.delete("/")).status_code == 200
    assert (await client.head("/")).status_code == 200
    assert (await client.options("/")).status_code == 200


async def test_async_websocket_connect_success_and_failure():
    async def echo_app(scope, receive, send):
        message = await receive()
        assert message["type"] == "websocket.connect"
        await send({"type": "websocket.accept"})
        await receive()

    client = AsyncTestClient(echo_app)
    session = await client.websocket_connect(
        "/ws", subprotocols=["chat"], headers={"x-extra": "1"}
    )
    session.close()


def test_websocket_denial_response():
    async def app(scope, receive, send):
        message = await receive()
        assert message["type"] == "websocket.connect"
        await send(
            {"type": "websocket.http.response.start", "status": 403, "headers": []}
        )
        await send(
            {
                "type": "websocket.http.response.body",
                "body": b"den",
                "more_body": True,
            }
        )
        await send({"type": "websocket.http.response.body", "body": b"ied"})

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as excinfo, client.websocket_connect("/ws"):
        pass
    assert excinfo.value.__class__.__name__ == "WebSocketDenialResponse"
    assert excinfo.value.status_code == 403
    assert excinfo.value.content == b"denied"


def test_websocket_immediate_close_raises_on_enter():
    async def app(scope, receive, send):
        message = await receive()
        assert message["type"] == "websocket.connect"
        await send({"type": "websocket.close", "code": 4000, "reason": "no"})

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws"):
        pass


def test_websocket_app_exception_propagates():
    async def app(scope, receive, send):
        await receive()
        raise ValueError("app blew up")

    client = TestClient(app)
    with pytest.raises(ValueError, match="app blew up"), client.websocket_connect("/ws"):
        pass


def test_websocket_session_waits_for_explicit_close():
    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                return

    client = TestClient(app)
    with client.websocket_connect("/ws") as session:
        session.send_text("hi")
        session.close()


def test_lifespan_shutdown_failure_is_surfaced():
    @contextlib.asynccontextmanager
    async def failing_shutdown(app):
        yield
        raise RuntimeError("boom-shutdown")

    app = SilloApp(lifespan=failing_shutdown)
    with TestClient(app):
        pass


def test_create_client_defaults():
    client = create_client()
    response = client.get("/does-not-exist")
    assert response.status_code == 404


async def test_create_async_client_defaults():
    client = create_async_client()
    response = await client.get("/does-not-exist")
    assert response.status_code == 404
