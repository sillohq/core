"""The built-in error layers are raw ASGI, and ``use()`` can register more.

``ServerErrorMiddleware`` and ``ExceptionMiddleware`` used to be dispatch
middleware — ``(request, call_next)`` — wrapped in a bridge that
built a ``HttpContext``, a ``Response``, an ``anyio.Event``, a memory object stream
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

import anyio
import pytest

from sillo import SilloApp, json
from sillo.core.error.handler import ServerErrorMiddleware
from sillo.core.http import HttpContext
from sillo.exception_handler import ExceptionMiddleware
from sillo.exceptions import HTTPException
from sillo.middleware.base import BaseMiddleware
from sillo.middleware.bridge import ASGIRequestResponseBridge
from sillo.middleware.define import (
    _is_prebuilt_raw_instance,
    _is_raw_asgi_middleware,
    _rebinding_factory,
    _runtime_call_signature,
)
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

    async def dispatch(self, ctx, call_next):
        ctx.scope.setdefault("tags", []).append(self.tag)
        return await call_next()


class StampHeader:
    """A raw ASGI middleware in the ordinary shape: factory taking the next app."""

    def __init__(
        self, app: ASGIApp, header: str = "x-stamp", value: str = "on"
    ) -> None:
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


def stamp_header_factory(app: ASGIApp) -> ASGIApp:
    """A raw ASGI middleware as a bare factory function, not a class.

    The ordinary shape third-party ASGI middleware from other frameworks
    ships in: a function taking the next app and returning the actual
    ``(scope, receive, send)`` callable, with nothing to construct.
    """

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        async def send_stamped(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"].append((b"x-stamp", b"on"))
            await send(message)

        await app(scope, receive, send_stamped)

    return middleware


def _app(**kwargs) -> SilloApp:
    app = SilloApp(**{"debug": False, **kwargs})

    @app.get("/ping")
    async def ping(ctx: HttpContext):
        return json({"tags": ctx.scope.get("tags", [])})

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
        async def boom(ctx: HttpContext):
            raise RuntimeError("kaboom")

        @app.get("/teapot")
        async def teapot(ctx: HttpContext):
            raise HTTPException(status_code=418, detail="teapot")

        @app.get("/custom")
        async def custom(ctx: HttpContext):
            raise Custom()

        async def custom_handler(ctx, exc):
            return json({"handled": "class"}, status_code=499)

        async def status_handler(ctx, exc):
            return json({"handled": "status"}, status_code=418)

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
        async def late(ctx: HttpContext):
            raise Late()

        with test_client_factory(app) as client:
            assert client.get("/late").status_code == 500

            async def handler(ctx, exc):
                return json({"late": True}, status_code=418)

            app.add_exception_handler(Late, handler)

            assert client.get("/late").status_code == 418

    def test_a_handler_survives_a_chain_rebuild(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()

        class Rebuilt(Exception):
            pass

        @app.get("/rebuilt")
        async def rebuilt(ctx: HttpContext):
            raise Rebuilt()

        async def handler(ctx, exc):
            return json({"ok": True}, status_code=418)

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
        # This is what "raw" buys: no HttpContext is constructed on its behalf,
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


class TestRawFactoryFunctionThroughUse:
    """A plain factory function, not a class, registered with raw=True.

    Distinct from `TestRawMiddlewareThroughUse`, which only ever registers a
    class: `use()` used to assume any non-class raw middleware was already a
    constructed instance (`inspect.isclass(middleware)` was the only check),
    so a bare factory function got rebound instead of called with the next
    app -- and blew up the first time a request reached it, since the
    function itself was then invoked as `fn(scope, receive, send)` instead of
    `fn(app)`.
    """

    def test_a_factory_function_runs(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(stamp_header_factory, raw=True)

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-stamp"] == "on"

    def test_it_is_not_wrapped_in_a_bridge(self):
        app = _app()
        app.use(stamp_header_factory, raw=True)

        assert not any(
            isinstance(layer, ASGIRequestResponseBridge) for layer in _layers(app)
        )

    def test_it_is_inferred_as_raw_without_raw_true(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        # Single required positional parameter (`app`) carries no structural
        # signal either way, so this stays an explicit-raw case rather than
        # an inference one -- documented here so the assumption is pinned.
        assert _is_raw_asgi_middleware(stamp_header_factory) is False

    def test_a_factory_function_and_a_class_factory_coexist(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(Tagging("dispatch"))
        app.use(stamp_header_factory, raw=True)
        app.use(StampHeader, raw=True, header="x-trace-id", value="abc123")

        with test_client_factory(app) as client:
            response = client.get("/ping")

        assert response.headers["x-stamp"] == "on"
        assert response.headers["x-trace-id"] == "abc123"
        assert response.json()["tags"] == ["dispatch"]


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

    The router builds one ``HttpContext``; an exception handler running after the
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
        async def raise_first(ctx: HttpContext):
            raise Boom()

        @app.post("/read-then-raise")
        async def read_then_raise(ctx: HttpContext):
            await ctx.json
            raise Boom()

        async def handler(ctx, exc):
            try:
                body = (await ctx.body).decode()
            except RuntimeError as error:
                body = f"RuntimeError: {error}"
            return json({"body": body}, status_code=400)

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
        async def echo(ctx: HttpContext):
            return json({"seen": await ctx.json})

        class Peeker(BaseMiddleware):
            async def dispatch(self, ctx, call_next):
                await ctx.body
                return await call_next()

        app.use(Peeker())

        with test_client_factory(app) as client:
            assert client.post("/echo", json={"a": 1}).json() == {"seen": {"a": 1}}


class TestAMiddlewareBuiltWithoutAnInnerApp:
    """Both take `app` optionally, so the failure has to name itself.

    `ServerErrorMiddleware` is constructed with no app on purpose — the debug
    page renderers are useful on their own — and `ExceptionMiddleware` exists
    before the application has a chain to put it in. Calling either in that
    state would otherwise surface as "'NoneType' object is not callable" from
    somewhere deep in the ASGI stack.
    """

    @staticmethod
    def _serve(middleware) -> None:
        scope = {"type": "http", "path": "/", "method": "GET", "headers": []}

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            pass

        anyio.run(middleware.__call__, scope, receive, send)

    def test_the_server_error_layer_says_so(self):
        with pytest.raises(RuntimeError, match="without an inner application"):
            self._serve(ServerErrorMiddleware())

    def test_the_exception_layer_says_so(self):
        with pytest.raises(RuntimeError, match="without an inner application"):
            self._serve(ExceptionMiddleware())

    def test_the_renderer_is_still_usable_without_one(self):
        # The whole reason `app` is optional.
        assert "boom" in ServerErrorMiddleware(debug=True).generate_html(
            RuntimeError("boom"), None
        )


class TestRawIsInferredFromTheSignature:
    """`raw=` need not be passed at all: `use()` reads it off `__call__`."""

    def test_a_bare_asgi_factory_is_detected_as_raw(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(StampHeader)  # no raw=True

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-stamp"] == "on"

    def test_a_dispatch_instance_is_still_detected_as_dispatch(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(Tagging("inferred"))  # no raw=False

        with test_client_factory(app) as client:
            assert client.get("/ping").json()["tags"] == ["inferred"]

    def test_differently_named_parameters_are_still_read_as_asgi(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        class Renamed:
            def __init__(self, app: ASGIApp) -> None:
                self.app = app

            async def __call__(self, s: Scope, r: Receive, w: Send) -> None:
                await self.app(s, r, w)

        app = _app()
        app.use(Renamed)

        with test_client_factory(app) as client:
            assert client.get("/ping").status_code == 200

    def test_an_already_constructed_raw_instance_is_bound_and_used(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        # The registration style every built-in (SessionMiddleware and
        # friends) actually uses: a configured instance, not a bare class.
        stamp = StampHeader.__new__(StampHeader)
        stamp.header = b"x-stamp"
        stamp.value = b"on"

        app = _app()
        app.use(stamp)

        assert stamp.app is not None  # bound by use(), not by StampHeader.__init__

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-stamp"] == "on"

    def test_a_generic_signature_falls_back_to_dispatch(self):
        # (*args, **kwargs) carries no structural signal either way, so the
        # pre-existing dispatch default applies -- and dispatch rejects
        # what look like factory arguments, same as an explicit raw=False.
        class Generic:
            async def __call__(self, *args, **kwargs):
                pass

        app = _app()

        with pytest.raises(TypeError, match="raw ASGI middleware"):
            app.use(Generic(), "extra")

    def test_raw_can_still_be_stated_explicitly(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = _app()
        app.use(StampHeader, raw=True)

        with test_client_factory(app) as client:
            assert client.get("/ping").headers["x-stamp"] == "on"


class TestTheInferenceHelpersDirectly:
    """Unit-level coverage for the edge cases a full request never reaches."""

    def test_a_class_with_no_call_at_all_is_not_raw(self):
        # `getattr(cls, "__call__")` falls back to the metaclass's own
        # `__call__` (what makes `cls(...)` construct an instance in the
        # first place), so this reads as `(*args, **kwargs)` rather than
        # "no signature at all" -- which still isn't mistaken for either
        # shape, since a generic signature carries no structural signal.
        class NotCallable:
            pass

        assert _is_raw_asgi_middleware(NotCallable) is False

    def test_a_class_with_call_explicitly_set_to_none_is_not_raw(self):
        # `__call__ = None` is a real attribute, not a missing one, so
        # `getattr(cls, "__call__", None)` returns `None` for the value
        # rather than falling back to the metaclass's own `__call__` --
        # the one way this branch actually reads as "no signature".
        class NoCall:
            __call__ = None

        assert _runtime_call_signature(NoCall) is None
        assert _is_raw_asgi_middleware(NoCall) is False

    def test_a_signature_that_cannot_be_read_is_not_raw(self):
        # `dir`/`vars` are C callables `inspect.signature` cannot introspect
        # at all, raising `ValueError` rather than returning `(*args,
        # **kwargs)` -- the other way a callable can carry no structural
        # signal.
        assert _runtime_call_signature(dir) is None
        assert _is_raw_asgi_middleware(dir) is False

    def test_a_non_callable_instance_is_not_raw(self):
        assert _is_raw_asgi_middleware(object()) is False
        assert _runtime_call_signature(object()) is None

    def test_a_call_whose_signature_cannot_be_read_is_not_raw(self):
        # Built-in callables like `dict().__call__`... most C callables raise
        # ValueError from inspect.signature; `str.join` is a reliable one.
        assert _runtime_call_signature(str.join) is not None  # sanity: this one *can*
        assert (
            _is_raw_asgi_middleware(len) is False
        )  # len() -- signature-less in CPython

    def test_four_required_positional_parameters_is_neither_shape(self):
        class FourParams:
            async def __call__(self, a, b, c, d):
                pass

        assert _is_raw_asgi_middleware(FourParams) is False

    def test_rebinding_factory_sets_app_and_returns_the_same_instance(self):
        class Recorder:
            app = None

            async def __call__(self, scope, receive, send):
                pass

        instance = Recorder()
        factory = _rebinding_factory(instance)

        sentinel = object()
        result = factory(sentinel)

        assert result is instance
        assert instance.app is sentinel

    def test_a_class_is_never_a_prebuilt_instance(self):
        # A class is always a factory still awaiting `next_app`, regardless
        # of what its instances' `__call__` looks like.
        assert _is_prebuilt_raw_instance(StampHeader) is False

    def test_a_factory_function_is_not_a_prebuilt_instance(self):
        # One required positional parameter (`app`) -- a factory awaiting
        # the next app, not an ASGI app already built.
        assert _is_prebuilt_raw_instance(stamp_header_factory) is False

    def test_an_already_built_instance_is_a_prebuilt_instance(self):
        # Three required positional parameters on its own `__call__`
        # (`scope, receive, send`) -- already shaped like the ASGI app it is.
        class Recorder:
            app = None

            async def __call__(self, scope, receive, send):
                pass

        assert _is_prebuilt_raw_instance(Recorder()) is True
