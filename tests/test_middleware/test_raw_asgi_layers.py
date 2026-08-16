"""The built-in error layers are raw ASGI, and ``use()`` can register more.

``ServerErrorMiddleware`` and ``ExceptionMiddleware`` used to be dispatch
middleware — ``(request, response, call_next)`` — wrapped in a bridge that
built a ``Request``, a ``Response``, an ``anyio.Event``, a memory object stream
and a background task for each of them, on every request. Neither ever wanted
any of it: both only care about a request that raised.

They are now plain ASGI middleware, ``__init__(app, ...)`` and
``__call__(scope, receive, send)``, constructing a request and a response only
inside their ``except`` clause. The tests below pin the behaviour that has to
survive that: every error path still produces the same response, handlers
registered after the chain is built still fire, and the ``raw=`` flag on
``use()`` puts user middleware on the same footing.
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo._internals._middleware import ASGIRequestResponseBridge
from sillo.core.error.handler import ServerErrorMiddleware
from sillo.core.http import Request, Response
from sillo.exception_handler import ExceptionMiddleware
from sillo.exceptions import HTTPException
from sillo.middleware.base import BaseMiddleware
from sillo.testclient import TestClient
from sillo.types import ASGIApp, Message, Receive, Scope, Send


def _layers(app: SilloApp) -> list[object]:
    """Walk the assembled chain from outermost inwards."""
    layers: list[object] = []
    node: object | None = app._request_chain
    while node is not None and hasattr(node, "app"):
        layers.append(node)
        node = node.app
    return layers


class Tagging(BaseMiddleware):
    """A dispatch-form middleware, so both forms can be observed together."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def process_request(self, request, response, call_next):
        request.scope.setdefault("tags", []).append(self.tag)
        return await call_next()


class StampHeader:
    """A raw ASGI middleware in the ordinary shape: factory taking the next app."""

    def __init__(self, app: ASGIApp, header: str = "x-stamp", value: str = "on") -> None:
        self.app = app
        self.header = header.encode()
        self.value = value.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_stamped(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"].append((self.header, self.value))
            await send(message)

        await self.app(scope, receive, send_stamped)


def _app(**kwargs) -> SilloApp:
    app = SilloApp(**{"debug": False, **kwargs})

    @app.get("/ping")
    async def ping(request: Request, response: Response):
        return response.json({"tags": request.scope.get("tags", [])})

    return app


class TestTheBuiltInLayersAreRawASGI:
    def test_the_chain_has_no_bridge_around_them(self):
        app = _app()

        assert not any(
            isinstance(layer, ASGIRequestResponseBridge) for layer in _layers(app)
        )

    def test_they_sit_outermost_and_innermost_of_the_user_stack(self):
        app = _app()
        app.use(Tagging("a"))

        layers = _layers(app)

        assert isinstance(layers[0], ServerErrorMiddleware)
        assert isinstance(layers[1], ASGIRequestResponseBridge)  # the dispatch one
        assert isinstance(layers[2], ExceptionMiddleware)

    def test_they_are_callable_as_asgi_applications(self):
        app = _app()

        for layer in _layers(app)[:1] + _layers(app)[-1:]:
            assert callable(layer)


class TestEveryErrorPathStillAnswers:
    """The point of the rewrite is that none of this changes."""

    @pytest.fixture
    def client(self, test_client_factory: Callable[[SilloApp], TestClient]):
        app = _app()

        class Custom(Exception):
            pass

        @app.get("/boom")
        async def boom(request: Request, response: Response):
            raise RuntimeError("kaboom")

        @app.get("/teapot")
        async def teapot(request: Request, response: Response):
            raise HTTPException(status_code=418, detail="teapot")

        @app.get("/custom")
        async def custom(request: Request, response: Response):
            raise Custom()

        async def custom_handler(request, response, exc):
            return response.json({"handled": "class"}, status_code=499)

        async def status_handler(request, response, exc):
            return response.json({"handled": "status"}, status_code=418)

        app.add_exception_handler(Custom, custom_handler)
        app.add_exception_handler(418, status_handler)

        with test_client_factory(app) as client:
            yield client

    def test_a_successful_request_is_untouched(self, client):
        assert client.get("/ping").status_code == 200

    def test_an_unhandled_exception_becomes_a_500(self, client):
        assert client.get("/boom").status_code == 500

    def test_a_class_handler_answers(self, client):
        response = client.get("/custom")
        assert response.status_code == 499
        assert response.json() == {"handled": "class"}

    def test_a_status_handler_wins_over_the_default_http_handler(self, client):
        response = client.get("/teapot")
        assert response.status_code == 418
        assert response.json() == {"handled": "status"}

    def test_an_unrouted_path_is_still_a_404(self, client):
        assert client.get("/nowhere").status_code == 404


class TestHandlersRegisteredAfterTheChainExists:
    """The exception middleware owns registries that outlive any one chain.

    It is rebound to the new inner app on every rebuild rather than
    reconstructed, because `setup_record` and the admin panel both register
    handlers while the application is still being configured — and the admin
    does it from a startup hook, after the chain already exists.
    """

    def test_a_handler_added_after_the_first_request_still_fires(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()

        class Late(Exception):
            pass

        @app.get("/late")
        async def late(request: Request, response: Response):
            raise Late()

        with test_client_factory(app) as client:
            assert client.get("/late").status_code == 500

            async def handler(request, response, exc):
                return response.json({"late": True}, status_code=418)

            app.add_exception_handler(Late, handler)

            assert client.get("/late").status_code == 418

    def test_a_handler_survives_a_chain_rebuild(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()

        class Rebuilt(Exception):
            pass

        @app.get("/rebuilt")
        async def rebuilt(request: Request, response: Response):
            raise Rebuilt()

        async def handler(request, response, exc):
            return response.json({"ok": True}, status_code=418)

        app.add_exception_handler(Rebuilt, handler)
        app.use(Tagging("forces-a-rebuild"))

        with test_client_factory(app) as client:
            assert client.get("/rebuilt").status_code == 418


class TestRawMiddlewareThroughUse:
    def test_a_raw_middleware_runs(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(StampHeader, raw=True)

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-stamp"] == "on"

    def test_it_is_not_wrapped_in_a_bridge(self):
        app = _app()
        app.use(StampHeader, raw=True)

        assert any(isinstance(layer, StampHeader) for layer in _layers(app))
        assert not any(
            isinstance(layer, ASGIRequestResponseBridge) for layer in _layers(app)
        )

    def test_arguments_reach_the_factory(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(StampHeader, raw=True, header="x-trace-id", value="abc123")

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-trace-id"] == "abc123"

    def test_positional_arguments_reach_the_factory(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(StampHeader, "x-positional", raw=True)

        with test_client_factory(app) as client:
            assert "x-positional" in client.get("/ping").headers

    def test_raw_and_dispatch_middleware_coexist(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(Tagging("dispatch"))
        app.use(StampHeader, raw=True)

        with test_client_factory(app) as client:
            response = client.get("/ping")

        assert response.json()["tags"] == ["dispatch"]
        assert response.headers["x-stamp"] == "on"

    def test_registration_order_still_puts_the_newest_outermost(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(Tagging("first"))
        app.use(Tagging("second"))
        app.use(StampHeader, raw=True)

        with test_client_factory(app) as client:
            assert client.get("/ping").json()["tags"] == ["second", "first"]

    def test_registering_one_rebuilds_the_chain(self):
        app = _app()
        before = app._request_chain

        app.use(StampHeader, raw=True)

        assert app._request_chain is not before

    def test_it_is_handed_the_raw_scope_rather_than_a_request(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        # This is what "raw" buys: no Request is constructed on its behalf,
        # so it reads the scope dict the server passed in.
        app = _app()
        seen: list[tuple[str, str]] = []

        class Recording:
            def __init__(self, inner: ASGIApp) -> None:
                self.app = inner

            async def __call__(self, scope: Scope, receive: Receive, send: Send):
                seen.append((scope["type"], scope["path"]))
                await self.app(scope, receive, send)

        app.use(Recording, raw=True)

        with test_client_factory(app) as client:
            client.get("/ping")

        assert seen == [("http", "/ping")]


class TestExtraArgumentsWithoutRaw:
    """Silently dropping them would leave the middleware on its defaults."""

    def test_positional_arguments_are_refused(self):
        app = _app()

        with pytest.raises(TypeError, match="raw ASGI middleware"):
            app.use(Tagging("x"), "extra")

    def test_keyword_arguments_are_refused(self):
        app = _app()

        with pytest.raises(TypeError, match="raw ASGI middleware"):
            app.use(Tagging("x"), option=1)

    def test_the_chain_is_not_modified_by_a_refused_call(self):
        app = _app()
        before = app._request_chain

        with pytest.raises(TypeError):
            app.use(Tagging("x"), "extra")

        assert app._request_chain is before


class TestAnExceptionAfterTheResponseStarted:
    """Once the status line is on the wire it cannot be replaced with a 500."""

    def test_it_is_re_raised_rather_than_corrupting_the_response(self):
        class Started:
            def __init__(self, app: ASGIApp) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send):
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return
                await send(
                    {"type": "http.response.start", "status": 200, "headers": []}
                )
                raise RuntimeError("too late")

        app = _app()
        layer = ServerErrorMiddleware(Started(app), debug=False)

        with pytest.raises(RuntimeError, match="too late"), TestClient(layer) as client:
            client.get("/ping")


class TestTheDebugRendererIsStillUsableOnItsOwn:
    """Several callers build one purely to render a page, with no inner app."""

    def test_it_constructs_without_an_app(self):
        assert ServerErrorMiddleware(debug=True).debug is True

    def test_it_renders_html_for_an_exception(self):
        middleware = ServerErrorMiddleware(debug=True)

        html = middleware.generate_html(RuntimeError("boom"), None)

        assert "boom" in html


class TestReadingTheBodyFromAnExceptionHandler:
    """A body can only come off the wire once, and several requests share a scope.

    The router builds one ``Request``; an exception handler running after the
    route handler already drained the body gets another. Without the scope
    marker the second one awaits a ``receive`` that can never produce another
    chunk, and the request hangs until the client gives up. It fails fast
    instead — the same error a single request re-reading its own body raises.
    """

    @pytest.fixture
    def client(self, test_client_factory: Callable[[SilloApp], TestClient]):
        app = _app()

        class Boom(Exception):
            pass

        @app.post("/raise-first")
        async def raise_first(request: Request, response: Response):
            raise Boom()

        @app.post("/read-then-raise")
        async def read_then_raise(request: Request, response: Response):
            await request.json
            raise Boom()

        async def handler(request, response, exc):
            try:
                body = (await request.body).decode()
            except RuntimeError as error:
                body = f"RuntimeError: {error}"
            return response.json({"body": body}, status_code=400)

        app.add_exception_handler(Boom, handler)

        with test_client_factory(app) as client:
            yield client

    def test_an_unread_body_is_still_available(self, client):
        response = client.post("/raise-first", json={"hello": "world"})

        assert response.json() == {"body": '{"hello":"world"}'}

    def test_an_already_read_body_errors_instead_of_hanging(self, client):
        response = client.post("/read-then-raise", json={"hello": "world"})

        assert response.json() == {"body": "RuntimeError: Stream consumed"}

    def test_a_dispatch_middleware_peeking_still_leaves_it_for_the_handler(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        # The bridge buffers the body and replays it downstream, so the marker
        # must distinguish "drained" from "being replayed".
        app = _app()

        @app.post("/echo")
        async def echo(request: Request, response: Response):
            return response.json({"seen": await request.json})

        class Peeker(BaseMiddleware):
            async def process_request(self, request, response, call_next):
                await request.body
                return await call_next()

        app.use(Peeker())

        with test_client_factory(app) as client:
            assert client.post("/echo", json={"a": 1}).json() == {"seen": {"a": 1}}
