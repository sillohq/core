from contextlib import asynccontextmanager
from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.config.base import MakeConfig
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient
from nexios.websockets import WebSocket

app = NexiosApp()
nested_app = NexiosApp()
mounted_router = Router(prefix="/mounted_router")
ws_router = Router(prefix="/ws_router")


@app.get("/")
def index(request: Request, response: Response):
    return "hello world"


@app.post("/")
def post_index(request: Request, response: Response):
    return "post hello world"


@app.put("/")
def put_index(request: Request, response: Response):
    return "put hello world"


@app.delete("/")
def delete_index(request: Request, response: Response):
    return "delete hello world"


@app.head("/")
def head_index(request: Request, response: Response):
    return ""  # return empty response


@app.options("/")
def options_index(request: Request, response: Response):
    return ""  # return empty response


@app.patch("/")
def patch_index(request: Request, response: Response):
    return "patch hello world"


@app.route(
    "/multiple_methods",
    methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"],
)
def multiple_methods(request: Request, response: Response):
    return "multiple methods"


async def add_route_with_method_handler(request: Request, response: Response):
    return "hello world"


async def add_route_with_route_object(request: Request, response: Response):
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
def mounted_index(request: Request, response: Response):
    return "mounted hello world"


@app.post("/route-with-name", name="route-with-name")
def mounted_post_index(request: Request, response: Response):
    return "mounted post hello world"


@app.post("/route-with-name-and-param/{param}", name="route-with-name-and-param")
def mounted_post_index_with_param(request: Request, response: Response, param: str):

    return "mounted post hello world with param: " + param


@nested_app.get("/")
async def get_nested_index(request, response):
    return "this is nested app"


@app.ws_route("/")
async def websocket_index(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


@ws_router.ws_route("/")
async def websocket_index2(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


app.mount_router(mounted_router)
app.mount_router(ws_router)
app.register(nested_app, "/nested")


@pytest.fixture
def client(test_client_factory: Callable[[NexiosApp], TestClient]):
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

    async def index1(request: Request, response: Response):
        return "hello world"

    async def index2(request: Request, response: Response):
        return "hello world"

    config = MakeConfig(
        debug=True,
        is_test=True,
    )
    routes = [
        Route(path="/", handler=index1, methods=["GET"]),
        Route(path="/index2", handler=index2, methods=["GET"]),
    ]
    app = NexiosApp(routes=routes, config=config)
    for route in routes:
        assert route in app.router.routes
    assert len(app.router.routes) >= len(routes)
    assert app.config.debug == config.debug
    assert app.config.is_test == config.is_test


# ========== Lifespan Tests ==========


def test_on_startup_handler():
    """Test that on_startup handlers are executed during application startup"""
    startup_called = {"value": False}

    test_app = NexiosApp()

    @test_app.on_startup
    async def startup_handler():
        startup_called["value"] = True

    @test_app.get("/test")
    async def test_route(request: Request, response: Response):
        return response.json({"startup": startup_called["value"]})

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

    test_app = NexiosApp()

    @test_app.on_shutdown
    async def shutdown_handler():
        shutdown_called["value"] = True

    @test_app.get("/test")
    async def test_route(request: Request, response: Response):
        return response.text("ok")

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

    test_app = NexiosApp()

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

    test_app = NexiosApp()

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

    test_app = NexiosApp()

    @test_app.on_startup
    async def startup_handler():
        state["started"] = True
        state["counter"] = 100

    @test_app.on_shutdown
    async def shutdown_handler():
        state["stopped"] = True
        state["counter"] = 0

    @test_app.get("/state")
    async def get_state(request: Request, response: Response):
        return response.json(state)

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
    async def lifespan(app: NexiosApp):
        # Startup
        state["db_connected"] = True
        state["cache_loaded"] = True
        app.state["custom_data"] = "initialized"

        yield {"db": "connected", "cache": "ready"}

        # Shutdown
        state["db_connected"] = False
        state["cache_loaded"] = False

    test_app = NexiosApp(lifespan=lifespan)

    @test_app.get("/status")
    async def status(request: Request, response: Response):
        return response.json(
            {
                "db": state["db_connected"],
                "cache": state["cache_loaded"],
                "app_state": request.scope.get("global_state", {}),
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
    async def lifespan(app: NexiosApp):
        # Startup - populate state
        app.state["database"] = "postgresql://localhost"
        app.state["api_key"] = "secret-key-123"

        yield {"initialized": True}

        # Shutdown - cleanup state
        app.state.clear()

    test_app = NexiosApp(lifespan=lifespan)

    @test_app.get("/config")
    async def get_config(request: Request, response: Response):
        global_state = request.scope.get("global_state", {})
        return response.json(
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
    async def lifespan(app: NexiosApp):
        # Custom lifespan logic
        yield

    test_app = NexiosApp(lifespan=lifespan)

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
    async def lifespan(app: NexiosApp):
        yield

    test_app = NexiosApp(lifespan=lifespan)

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
    async def lifespan(app: NexiosApp):
        app.state["service"] = "active"
        yield
        app.state["service"] = "inactive"

    test_app = NexiosApp(lifespan=lifespan)

    @test_app.get("/increment")
    async def increment(request: Request, response: Response):
        request_count["value"] += 1
        return response.json(
            {
                "count": request_count["value"],
                "service": request.scope.get("global_state", {}).get("service"),
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
    async def lifespan(app: NexiosApp):
        app.state["counter"] = 0
        app.state["requests"] = []
        yield

    test_app = NexiosApp(lifespan=lifespan)

    @test_app.post("/track")
    async def track(request: Request, response: Response):
        global_state = request.scope.get("global_state", {})
        global_state["counter"] = global_state.get("counter", 0) + 1
        global_state["requests"].append(request.url.path)
        return response.json(
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
