"""``sillo._internals._middleware`` — the bridge and its cached request.

Most of this module is a state machine that only runs on the awkward paths: a
client that disconnects mid-body, a middleware that reads the body and then
hands it downstream, an inner application that raises before sending anything.
Those are exactly the paths a normal request never takes, which is why they
were unreached.
"""

import anyio
import pytest

from sillo import SilloApp
from sillo._internals._middleware import (
    ASGIRequestResponseBridge,
    DefineMiddleware,
    _CachedRequest,
)
from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware
from sillo.testclient import TestClient


def http_scope(**overrides):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1),
        "server": ("t", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }
    scope.update(overrides)
    return scope


def receiver(*messages):
    """A receive callable that yields *messages* then blocks forever."""
    queue = list(messages)

    async def receive():
        if queue:
            return queue.pop(0)
        await anyio.sleep_forever()

    return receive


class TestDefineMiddlewareRepr:
    def test_it_names_the_middleware_class(self):
        text = repr(DefineMiddleware(BaseMiddleware))
        assert "DefineMiddleware(" in text
        assert "BaseMiddleware" in text

    def test_positional_arguments_appear(self):
        assert "42" in repr(DefineMiddleware(BaseMiddleware, 42))

    def test_keyword_arguments_appear_as_pairs(self):
        assert "flag=True" in repr(DefineMiddleware(BaseMiddleware, flag=True))

    def test_a_class_without_a_name_still_renders(self):
        class Odd:
            pass

        Odd.__name__ = ""
        assert repr(DefineMiddleware(Odd)).startswith("DefineMiddleware(")

    def test_it_unpacks_like_a_tuple(self):
        cls, args, kwargs = DefineMiddleware(BaseMiddleware, 1, key="v")

        assert cls is BaseMiddleware
        assert args == (1,)
        assert kwargs == {"key": "v"}


class TestCachedRequestReceive:
    async def test_an_unread_body_is_streamed_through(self):
        request = _CachedRequest(
            http_scope(),
            receiver({"type": "http.request", "body": b"chunk", "more_body": False}),
        )

        message = await request.wrapped_receive()

        assert message["type"] == "http.request"
        assert message["body"] == b"chunk"

    async def test_a_body_already_read_is_replayed_downstream(self):
        request = _CachedRequest(
            http_scope(),
            receiver({"type": "http.request", "body": b"payload", "more_body": False}),
        )
        await request.body

        message = await request.wrapped_receive()

        assert message["body"] == b"payload"
        assert message["more_body"] is False

    async def test_a_consumed_stream_yields_an_empty_body(self):
        # stream() to completion means the bytes are gone; downstream gets an
        # empty body rather than hanging waiting for one.
        request = _CachedRequest(
            http_scope(),
            receiver({"type": "http.request", "body": b"gone", "more_body": False}),
        )
        async for _ in request.stream():
            pass

        message = await request.wrapped_receive()

        assert message["type"] == "http.request"
        assert message["body"] == b""

    async def test_a_replayed_body_is_followed_by_a_disconnect(self):
        request = _CachedRequest(
            http_scope(),
            receiver(
                {"type": "http.request", "body": b"payload", "more_body": False},
                {"type": "http.disconnect"},
            ),
        )
        await request.body
        await request.wrapped_receive()

        assert (await request.wrapped_receive())["type"] == "http.disconnect"

    async def test_the_disconnect_is_repeated_without_waiting(self):
        request = _CachedRequest(
            http_scope(),
            receiver(
                {"type": "http.request", "body": b"payload", "more_body": False},
                {"type": "http.disconnect"},
            ),
        )
        await request.body
        await request.wrapped_receive()
        await request.wrapped_receive()

        # The third call must not block on a receive that will never come.
        with anyio.fail_after(1):
            assert (await request.wrapped_receive())["type"] == "http.disconnect"

    async def test_a_disconnect_while_streaming_is_reported(self):
        request = _CachedRequest(
            http_scope(), receiver({"type": "http.disconnect"})
        )

        assert (await request.wrapped_receive())["type"] == "http.disconnect"


class TestBridgeRepr:
    def test_it_names_the_inner_app_and_dispatch(self):
        async def inner(scope, receive, send):
            return None

        async def dispatch(request, response, call_next):
            return await call_next()

        # The bridge formats itself through __str__, not __repr__.
        text = str(ASGIRequestResponseBridge(inner, dispatch))

        assert text.startswith("ASGIRequestResponseBridge(")


class TestBridgePassthrough:
    async def test_a_non_http_scope_goes_straight_to_the_inner_app(self):
        seen = {}

        async def inner(scope, receive, send):
            seen["type"] = scope["type"]

        async def dispatch(request, response, call_next):  # pragma: no cover
            raise AssertionError("dispatch must not run for a lifespan scope")

        bridge = ASGIRequestResponseBridge(inner, dispatch)

        async def receive():
            return {"type": "lifespan.startup"}

        async def send(message):
            return None

        await bridge({"type": "lifespan"}, receive, send)

        assert seen["type"] == "lifespan"


class TestExceptionsThroughTheBridge:
    def test_an_inner_exception_reaches_the_client_as_a_500(self):
        app = SilloApp(debug=False)

        @app.get("/boom")
        async def boom(request: Request, response: Response):
            raise RuntimeError("inner failure")

        class Passthrough(BaseMiddleware):
            async def process_request(self, request, response, call_next):
                return await call_next()

        app.use(Passthrough())

        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/boom").status_code == 500

    def test_a_middleware_can_short_circuit_without_calling_next(self):
        app = SilloApp(debug=False)

        @app.get("/never")
        async def never(request: Request, response: Response):  # pragma: no cover
            raise AssertionError("the handler must not run")

        class Blocker(BaseMiddleware):
            async def process_request(self, request, response, call_next):
                return response.json({"blocked": True}, status_code=403)

        app.use(Blocker())

        with TestClient(app) as client:
            result = client.get("/never")

        assert result.status_code == 403
        assert result.json() == {"blocked": True}

    def test_a_middleware_reading_the_body_still_leaves_it_for_the_handler(self):
        app = SilloApp(debug=False)

        @app.post("/echo")
        async def echo(request: Request, response: Response):
            return response.json({"seen": await request.json})

        class Peeker(BaseMiddleware):
            async def process_request(self, request, response, call_next):
                await request.body
                return await call_next()

        app.use(Peeker())

        with TestClient(app) as client:
            result = client.post("/echo", json={"a": 1})

        assert result.json() == {"seen": {"a": 1}}
