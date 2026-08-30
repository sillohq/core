from contextlib import asynccontextmanager, contextmanager
from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json, text
from sillo.core.http import HttpContext
from sillo.core.routing import Group, Route, Router
from sillo.testclient import TestClient
from sillo.websockets import WebSocketContext

app = SilloApp()
nested_app = SilloApp()
mounted_router = Router(prefix="/mounted_router")
ws_router = Router(prefix="/ws_router")


@app.get("/")
def index(ctx: HttpContext):
    return "hello world"


@app.post("/")
def post_index(ctx: HttpContext):
    return "post hello world"


@app.put("/")
def put_index(ctx: HttpContext):
    return "put hello world"


@app.delete("/")
def delete_index(ctx: HttpContext):
    return "delete hello world"


@app.head("/")
def head_index(ctx: HttpContext):
    return ""  # return empty response


@app.options("/")
def options_index(ctx: HttpContext):
    return ""  # return empty response


@app.patch("/")
def patch_index(ctx: HttpContext):
    return "patch hello world"


@app.route(
    "/multiple_methods",
    methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"],
)
def multiple_methods(ctx: HttpContext):
    return "multiple methods"


async def add_route_with_method_handler(ctx: HttpContext):
    return "hello world"


async def add_route_with_route_object(ctx: HttpContext):
    return "hello world"


app.add_route(
    path="/add_route_with_method_handler",
    handler=add_route_with_method_handler,
    methods=["GET"],
)

app.add_route(
    Route(
        path="/add_route_with_route_object",
        handler=add_route_with_route_object,
        methods=["GET"],
    )
)


@mounted_router.get("/")
def mounted_index(ctx: HttpContext):
    return "mounted hello world"


@app.post("/route-with-name", name="route-with-name")
def mounted_post_index(ctx: HttpContext):
    return "mounted post hello world"


@app.post("/route-with-name-and-param/{param}", name="route-with-name-and-param")
def mounted_post_index_with_param(ctx: HttpContext, param: str):

    return "mounted post hello world with param: " + param


@nested_app.get("/")
async def get_nested_index(ctx):
    return "this is nested app"


@app.ws_route("/")
async def websocket_index(websocket: WebSocketContext):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


@ws_router.ws_route("/")
async def websocket_index2(websocket: WebSocketContext):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


app.mount_router(mounted_router)
app.mount_router(ws_router)
nested_group = Group(path="/nested", app=nested_app)
app.add_route(nested_group)


@pytest.fixture
def client(test_client_factory: Callable[[SilloApp], TestClient]):
    with test_client_factory(app) as client:
        yield client


def test_get(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "hello world"


def test_post(client: TestClient):
    response = client.post("/")
    assert response.status_code == 200
    assert response.text == "post hello world"


def test_put(client: TestClient):
    response = client.put("/")
    assert response.status_code == 200
    assert response.text == "put hello world"


def test_delete(client: TestClient):
    response = client.delete("/")
    assert response.status_code == 200
    assert response.text == "delete hello world"


def test_head(client: TestClient):
    response = client.head("/")
    assert response.status_code == 200
    assert response.text == ""


def test_options(client: TestClient):
    response = client.options("/")
    assert response.status_code == 200
    assert response.text == ""


def test_patch(client: TestClient):
    response = client.patch("/")
    assert response.status_code == 200
    assert response.text == "patch hello world"


def test_multiple_methods(client: TestClient):
    response = client.get("/multiple_methods")
    assert response.status_code == 200
    assert response.text == "multiple methods"


def test_add_route_with_method_handler(client: TestClient):
    response = client.get("/add_route_with_method_handler")
    assert response.status_code == 200
    assert response.text == "hello world"


def test_add_route_with_route_object(client: TestClient):
    response = client.get("/add_route_with_route_object")
    assert response.status_code == 200
    assert response.text == "hello world"


def test_mounted_router(client: TestClient):
    response = client.get("/mounted_router/")
    assert response.status_code == 200
    assert response.text == "mounted hello world"


def test_url_for(client: TestClient):
    assert app.url_for("route-with-name") == "/route-with-name"


def test_url_for_with_param(client: TestClient):
    assert (
        app.url_for("route-with-name-and-param", param="test")
        == "/route-with-name-and-param/test"
    )


def test_websocket(client: TestClient):
    with client.websocket_connect("/") as websocket:
        websocket.send_text("hello world")
        assert websocket.receive_text() == "Message text was: hello world"


def test_mounted_ws_router(client: TestClient):
    with client.websocket_connect("/ws_router/") as websocket:
        websocket.send_text("hello world")
        assert websocket.receive_text() == "Message text was: hello world"


def test_register_nested_app(client: TestClient):
    response = client.get("/nested/")
    assert response.status_code == 200
    assert response.text == "this is nested app"


def test_app_init():

    async def index1(ctx: HttpContext):
        return "hello world"

    async def index2(ctx: HttpContext):
        return "hello world"

    routes = [
        Route(path="/", handler=index1, methods=["GET"]),
        Route(path="/index2", handler=index2, methods=["GET"]),
    ]
    app = SilloApp(routes=routes)
    for route in routes:
        assert route in app.router.routes
    assert len(app.router.routes) >= len(routes)



# ========== Lifespan Tests ==========


def test_on_startup_handler():
    """Test that on_startup handlers are executed during application startup"""
    startup_called = {"value": False}

    test_app = SilloApp()

    @test_app.on_startup
    async def startup_handler():
        startup_called["value"] = True

    @test_app.get("/test")
    async def test_route(ctx: HttpContext):
        return json({"startup": startup_called["value"]})

    with TestClient(test_app) as client:
        # After entering context, startup should have been called
        assert startup_called["value"] is True

        # Make a request to verify app is working
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"startup": True}


def test_on_shutdown_handler():
    """Test that on_shutdown handlers are executed during application shutdown"""
    shutdown_called = {"value": False}

    test_app = SilloApp()

    @test_app.on_shutdown
    async def shutdown_handler():
        shutdown_called["value"] = True

    @test_app.get("/test")
    async def test_route(ctx: HttpContext):
        return text("ok")

    with TestClient(test_app) as client:
        # Shutdown should not have been called yet
        assert shutdown_called["value"] is False

        # Make a request to verify app is working
        resp = client.get("/test")
        assert resp.status_code == 200

    # After exiting context, shutdown should have been called
    assert shutdown_called["value"] is True


def test_multiple_startup_handlers():
    """Test that multiple on_startup handlers are executed in order"""
    execution_order = []

    test_app = SilloApp()

    @test_app.on_startup
    async def startup_handler_1():
        execution_order.append("first")

    @test_app.on_startup
    async def startup_handler_2():
        execution_order.append("second")

    @test_app.on_startup
    async def startup_handler_3():
        execution_order.append("third")

    with TestClient(test_app) as client:
        assert execution_order == ["first", "second", "third"]


def test_multiple_shutdown_handlers():
    """Test that multiple on_shutdown handlers are executed in order"""
    execution_order = []

    test_app = SilloApp()

    @test_app.on_shutdown
    async def shutdown_handler_1():
        execution_order.append("first")

    @test_app.on_shutdown
    async def shutdown_handler_2():
        execution_order.append("second")

    @test_app.on_shutdown
    async def shutdown_handler_3():
        execution_order.append("third")

    with TestClient(test_app) as client:
        pass

    assert execution_order == ["first", "second", "third"]


def test_startup_and_shutdown_together():
    """Test that both startup and shutdown handlers work together"""
    state = {"started": False, "stopped": False, "counter": 0}

    test_app = SilloApp()

    @test_app.on_startup
    async def startup_handler():
        state["started"] = True
        state["counter"] = 100

    @test_app.on_shutdown
    async def shutdown_handler():
        state["stopped"] = True
        state["counter"] = 0

    @test_app.get("/state")
    async def get_state(ctx: HttpContext):
        return json(state)

    with TestClient(test_app) as client:
        assert state["started"] is True
        assert state["stopped"] is False
        assert state["counter"] == 100

        resp = client.get("/state")
        assert resp.json()["started"] is True
        assert resp.json()["counter"] == 100

    assert state["stopped"] is True
    assert state["counter"] == 0


def test_lifespan_context_manager():
    """Test custom lifespan context manager"""
    state = {"db_connected": False, "cache_loaded": False}

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        # Startup
        state["db_connected"] = True
        state["cache_loaded"] = True
        app.state["custom_data"] = "initialized"

        yield {"db": "connected", "cache": "ready"}

        # Shutdown
        state["db_connected"] = False
        state["cache_loaded"] = False

    test_app = SilloApp(lifespan=lifespan)

    @test_app.get("/status")
    async def status(ctx: HttpContext):
        return json(
            {
                "db": state["db_connected"],
                "cache": state["cache_loaded"],
                "app_state": ctx.scope.get("global_state", {}),
            }
        )

    with TestClient(test_app) as client:
        assert state["db_connected"] is True
        assert state["cache_loaded"] is True

        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["db"] is True
        assert data["cache"] is True
        assert "db" in data["app_state"]
        assert data["app_state"]["db"] == "connected"

    # After shutdown
    assert state["db_connected"] is False
    assert state["cache_loaded"] is False


def test_lifespan_with_state():
    """Test that lifespan context manager can update app state"""

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        # Startup - populate state
        app.state["database"] = "postgresql://localhost"
        app.state["api_key"] = "secret-key-123"

        yield {"initialized": True}

        # Shutdown - cleanup state
        app.state.clear()

    test_app = SilloApp(lifespan=lifespan)

    @test_app.get("/config")
    async def get_config(ctx: HttpContext):
        global_state = ctx.scope.get("global_state", {})
        return json(
            {
                "database": global_state.get("database"),
                "api_key": global_state.get("api_key"),
                "initialized": global_state.get("initialized"),
            }
        )

    with TestClient(test_app) as client:
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] == "postgresql://localhost"
        assert data["api_key"] == "secret-key-123"
        assert data["initialized"] is True


def test_startup_handlers_not_called_with_lifespan():
    """Test that on_startup handlers are not called when lifespan context is provided"""
    startup_called = {"value": False}

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        # Custom lifespan logic
        yield

    test_app = SilloApp(lifespan=lifespan)

    @test_app.on_startup
    async def startup_handler():
        startup_called["value"] = True

    with TestClient(test_app) as client:
        # Startup handler should NOT be called when lifespan is provided
        assert startup_called["value"] is False


def test_shutdown_handlers_not_called_with_lifespan():
    """Test that on_shutdown handlers are not called when lifespan context is provided"""
    shutdown_called = {"value": False}

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        yield

    test_app = SilloApp(lifespan=lifespan)

    @test_app.on_shutdown
    async def shutdown_handler():
        shutdown_called["value"] = True

    with TestClient(test_app) as client:
        pass

    # Shutdown handler should NOT be called when lifespan is provided
    assert shutdown_called["value"] is False


def test_lifespan_with_routes():
    """Test that lifespan works correctly with regular routes"""
    request_count = {"value": 0}

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        app.state["service"] = "active"
        yield
        app.state["service"] = "inactive"

    test_app = SilloApp(lifespan=lifespan)

    @test_app.get("/increment")
    async def increment(ctx: HttpContext):
        request_count["value"] += 1
        return json(
            {
                "count": request_count["value"],
                "service": ctx.scope.get("global_state", {}).get("service"),
            }
        )

    with TestClient(test_app) as client:
        resp1 = client.get("/increment")
        assert resp1.json()["count"] == 1
        assert resp1.json()["service"] == "active"

        resp2 = client.get("/increment")
        assert resp2.json()["count"] == 2
        assert resp2.json()["service"] == "active"


def test_app_state_persistence():
    """Test that app state persists across requests during lifespan"""

    @asynccontextmanager
    async def lifespan(app: SilloApp):
        app.state["counter"] = 0
        app.state["requests"] = []
        yield

    test_app = SilloApp(lifespan=lifespan)

    @test_app.post("/track")
    async def track(ctx: HttpContext):
        global_state = ctx.scope.get("global_state", {})
        global_state["counter"] = global_state.get("counter", 0) + 1
        global_state["requests"].append(ctx.url.path)
        return json(
            {
                "counter": global_state["counter"],
                "total_requests": len(global_state["requests"]),
            }
        )

    with TestClient(test_app) as client:
        resp1 = client.post("/track")
        assert resp1.json()["counter"] == 1
        assert resp1.json()["total_requests"] == 1

        resp2 = client.post("/track")
        assert resp2.json()["counter"] == 2
        assert resp2.json()["total_requests"] == 2

        resp3 = client.post("/track")
        assert resp3.json()["counter"] == 3
        assert resp3.json()["total_requests"] == 3


# ========== Sync Context Manager Lifespan Tests ==========


def test_sync_lifespan_context_manager():
    """Test that a sync context manager works for lifespan"""
    state = {"startup": False, "shutdown": False}

    @contextmanager
    def lifespan(app: SilloApp):
        state["startup"] = True
        app.state["data"] = "from-sync"
        yield {"initialized": True}
        state["shutdown"] = True

    test_app = SilloApp(lifespan=lifespan)

    @test_app.get("/status")
    async def status(ctx: HttpContext):
        return json(
            {
                "data": ctx.scope.get("global_state", {}).get("data"),
                "initialized": ctx.scope.get("global_state", {}).get("initialized"),
            }
        )

    with TestClient(test_app) as client:
        assert state["startup"] is True

        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == "from-sync"
        assert data["initialized"] is True

    assert state["shutdown"] is True


def test_sync_lifespan_state_persistence():
    """Test that sync lifespan state persists across requests"""

    @contextmanager
    def lifespan(app: SilloApp):
        app.state["counter"] = 0
        yield

    test_app = SilloApp(lifespan=lifespan)

    @test_app.post("/inc")
    async def increment(ctx: HttpContext):
        global_state = ctx.scope.get("global_state", {})
        global_state["counter"] = global_state.get("counter", 0) + 1
        return json({"counter": global_state["counter"]})

    with TestClient(test_app) as client:
        resp1 = client.post("/inc")
        assert resp1.json()["counter"] == 1

        resp2 = client.post("/inc")
        assert resp2.json()["counter"] == 2


def test_sync_lifespan_with_yield_value():
    """Test that sync lifespan can pass state via yield"""

    @contextmanager
    def lifespan(app: SilloApp):
        yield {"db": "connected", "cache": "warm"}

    test_app = SilloApp(lifespan=lifespan)

    @test_app.get("/state")
    async def get_state(ctx: HttpContext):
        gs = ctx.scope.get("global_state", {})
        return json(gs)

    with TestClient(test_app) as client:
        resp = client.get("/state")
        assert resp.json()["db"] == "connected"
        assert resp.json()["cache"] == "warm"


def test_sync_lifespan_and_async_lifespan_both_work():
    """Test that both sync and async lifespan work correctly"""

    # Sync
    sync_state = {"ran": False}

    @contextmanager
    def sync_lifespan(app: SilloApp):
        sync_state["ran"] = True
        yield

    sync_app = SilloApp(lifespan=sync_lifespan)

    with TestClient(sync_app) as client:
        assert sync_state["ran"] is True

    # Async
    async_state = {"ran": False}

    @asynccontextmanager
    async def async_lifespan(app: SilloApp):
        async_state["ran"] = True
        yield

    async_app = SilloApp(lifespan=async_lifespan)

    with TestClient(async_app) as client:
        assert async_state["ran"] is True
