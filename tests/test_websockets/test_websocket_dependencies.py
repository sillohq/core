"""Dependency injection on WebSocket routes.

WebSocket handlers are analysed the same way HTTP handlers are, so they may
declare ``Depend(...)`` parameters. A dependency callable receives the live
``WebSocketContext`` as its first positional argument, exactly as the handler
does.
"""

from typing import Callable

from sillo import SilloApp
from sillo.core.dependencies import Depend
from sillo.testclient import TestClient
from sillo.websockets import WebSocketContext


def test_ws_depend_callable(test_client_factory: Callable[[SilloApp], TestClient]):
    """A plain Depend(callable) resolves and binds on a WebSocket route."""
    app = SilloApp()

    def get_greeting(_) -> str:
        return "hi"

    @app.ws_route("/ws/dep")
    async def endpoint(ws: WebSocketContext, greeting: str = Depend(get_greeting)):
        await ws.accept()
        await ws.send_text(greeting)
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/dep") as ws:
            assert ws.receive_text() == "hi"


def test_ws_depend_async_callable(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """An async Depend(callable) is awaited before the handler runs."""
    app = SilloApp()

    async def get_token(_) -> str:
        return "tok-42"

    @app.ws_route("/ws/async-dep")
    async def endpoint(ws: WebSocketContext, token: str = Depend(get_token)):
        await ws.accept()
        await ws.send_text(token)
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/async-dep") as ws:
            assert ws.receive_text() == "tok-42"


def test_ws_dependency_first_param_is_websocket_context(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A dependency's first parameter is the live WebSocketContext itself."""
    app = SilloApp()

    seen = {}

    def capture(ctx):
        seen["ctx"] = ctx
        return isinstance(ctx, WebSocketContext)

    @app.ws_route("/ws/ctx")
    async def endpoint(ws: WebSocketContext, is_ws_ctx: bool = Depend(capture)):
        await ws.accept()
        await ws.send_json(
            {
                "same_object": seen["ctx"] is ws,
                "is_ws_context": is_ws_ctx,
            }
        )
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/ctx") as ws:
            data = ws.receive_json()
            assert data["same_object"] is True
            assert data["is_ws_context"] is True


def test_ws_dependency_reads_off_its_context(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A sub-dependency reads request data off its WebSocketContext parameter."""
    app = SilloApp()

    def read_protocol(ctx: WebSocketContext) -> str:
        return ctx.headers.get("sec-websocket-protocol", "none")

    @app.ws_route("/ws/subdep")
    async def endpoint(ws: WebSocketContext, proto: str = Depend(read_protocol)):
        await ws.accept()
        await ws.send_text(proto)
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/subdep", subprotocols=["chat"]) as ws:
            assert ws.receive_text() == "chat"


def test_ws_depend_with_path_param(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Path parameters and Depend markers coexist on the same handler."""
    app = SilloApp()

    def get_prefix(_) -> str:
        return "room"

    @app.ws_route("/ws/room/{room_id}")
    async def endpoint(
        ws: WebSocketContext,
        room_id: str,
        prefix: str = Depend(get_prefix),
    ):
        await ws.accept()
        await ws.send_text(f"{prefix}:{room_id}")
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/room/42") as ws:
            assert ws.receive_text() == "room:42"


def test_ws_nested_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The full dependency tree is resolved deepest-first for a socket."""
    app = SilloApp()

    def get_config(_) -> dict:
        return {"env": "test"}

    def get_service(_, config: dict = Depend(get_config)) -> str:
        return f"service[{config['env']}]"

    @app.ws_route("/ws/nested")
    async def endpoint(ws: WebSocketContext, service: str = Depend(get_service)):
        await ws.accept()
        await ws.send_text(service)
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/nested") as ws:
            assert ws.receive_text() == "service[test]"


def test_ws_generator_dependency_is_torn_down(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A generator dependency yields its value, then closes after the handler."""
    events: list[str] = []

    app = SilloApp()

    def get_resource(_):
        events.append("open")
        try:
            yield "resource"
        finally:
            events.append("close")

    @app.ws_route("/ws/gen")
    async def endpoint(ws: WebSocketContext, res: str = Depend(get_resource)):
        await ws.accept()
        events.append(f"handler:{res}")
        await ws.send_text(res)
        await ws.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/gen") as ws:
            assert ws.receive_text() == "resource"

    assert events == ["open", "handler:resource", "close"]
