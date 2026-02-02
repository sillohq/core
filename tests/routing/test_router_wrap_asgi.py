import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Router
from nexios.testclient import TestClient
from nexios.types import ASGIApp, Receive, Scope, Send


def test_router_wrap_asgi_basic(test_client_factory):
    app = NexiosApp()
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
    async def handler(request: Request, response: Response):
        executed.append("handler")
        return response.json({"message": "ok"})

    # Use wrap_asgi on the router
    router.wrap_asgi(SimpleMiddleware)
    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "middleware" in executed
        assert "handler" in executed


def test_router_wrap_asgi_websocket(test_client_factory):
    app = NexiosApp()
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

    router.wrap_asgi(WSMiddleware)
    app.mount_router(router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/echo"):
            pass

        assert "ws_middleware" in executed
        assert "handler" in executed
