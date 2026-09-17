import pytest

from sillo import SilloApp, json
from sillo.core.http import HttpContext
from sillo.core.routing import Router
from sillo.testclient import TestClient
from sillo.types import ASGIApp, Receive, Scope, Send


def test_router_use_raw_basic(test_client_factory):
    app = SilloApp()
    router = Router(prefix="/api")

    executed = []

    class SimpleMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                executed.append("middleware")
            await self.app(scope, receive, send)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    # Use raw ASGI middleware on the router
    router.use(SimpleMiddleware)
    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "middleware" in executed
        assert "handler" in executed


def test_router_use_raw_websocket(test_client_factory):
    app = SilloApp()
    router = Router(prefix="/ws")

    executed = []

    class WSMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "websocket":
                executed.append("ws_middleware")
            await self.app(scope, receive, send)

    @router.ws_route("/echo")
    async def echo_handler(websocket):
        await websocket.accept()
        executed.append("handler")
        await websocket.close()

    router.use(WSMiddleware)
    app.mount_router(router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/echo"):
            pass

        assert "ws_middleware" in executed
        assert "handler" in executed


def test_router_use_raw_with_kwargs(test_client_factory):
    app = SilloApp()
    router = Router(prefix="/api")

    class HeaderMiddleware:
        def __init__(self, app: ASGIApp, header: str = "x-default"):
            self.app = app
            self.header = header.encode()

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((self.header, b"present"))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    router.use(HeaderMiddleware, header="x-router-header")
    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.headers.get("x-router-header") == "present"


def test_router_use_raw_constructed_instance(test_client_factory):
    app = SilloApp()
    router = Router(prefix="/api")

    executed = []

    class MarkerMiddleware:
        app = None

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                executed.append("marker")
            await self.app(scope, receive, send)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    # An already-constructed instance is rebound via a one-shot factory.
    router.use(MarkerMiddleware())
    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "marker" in executed


def test_router_use_guard_errors():
    router = Router(prefix="/api")

    async def dispatch_middleware(ctx, call_next):
        return await call_next()

    with pytest.raises(TypeError):
        router.use(dispatch_middleware, "extra")

    class RawMiddleware:
        app = None

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    with pytest.raises(TypeError):
        router.use(RawMiddleware(), "extra")