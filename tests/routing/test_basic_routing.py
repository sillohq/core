"""
Tests for basic Router and Route functionality
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient

# ========== Basic Router Tests ==========


def test_router_initialization():
    """Test basic router initialization"""
    router = Router()
    assert router.prefix == ""
    assert router.routes == []
    assert router.middleware == []


def test_router_with_prefix():
    """Test router initialization with prefix"""
    router = Router(prefix="/api")
    assert router.prefix == "/api"


def test_router_with_routes():
    """Test router initialization with routes"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"])
    router = Router(routes=[route])

    assert len(router.routes) >= 1
    assert route in router.routes


def test_router_with_tags():
    """Test router initialization with tags"""
    router = Router(tags=["api", "v1"])
    assert "api" in router.tags
    assert "v1" in router.tags


def test_router_with_name():
    """Test router initialization with name"""
    router = Router(name="main-router")
    assert router.name == "main-router"


# ========== Basic Route Tests ==========


def test_route_initialization():
    """Test basic route initialization"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"])

    assert route.raw_path == "/test"
    assert route.handler is not None
    assert "GET" in [m.upper() for m in route.methods]


def test_route_with_name():
    """Test route initialization with name"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"], name="test-route")
    assert route.name == "test-route"


def test_route_with_summary_and_description():
    """Test route with OpenAPI documentation"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route(
        "/test",
        handler,
        methods=["GET"],
        summary="Test endpoint",
        description="This is a test endpoint",
    )

    assert route.summary == "Test endpoint"
    assert route.description == "This is a test endpoint"


def test_route_with_tags():
    """Test route with tags"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"], tags=["test", "api"])
    assert "test" in route.tags
    assert "api" in route.tags


def test_route_deprecated_flag():
    """Test route deprecation flag"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"], deprecated=True)
    assert route.deprecated is True


def test_route_exclude_from_schema():
    """Test route exclusion from OpenAPI schema"""

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"], exclude_from_schema=True)
    assert route.exclude_from_schema is True


# ========== Router Add Route Tests ==========


def test_router_add_route_with_route_object():
    """Test adding route using Route object"""
    router = Router()

    async def handler(request: Request, response: Response):
        return response.text("test")

    route = Route("/test", handler, methods=["GET"])
    router.add_route(route)

    assert route in router.routes


def test_router_add_route_with_parameters():
    """Test adding route using parameters"""
    router = Router()

    async def handler(request: Request, response: Response):
        return response.text("test")

    router.add_route(path="/test", handler=handler, methods=["GET"])

    assert len(router.routes) >= 1


def test_router_add_multiple_routes():
    """Test adding multiple routes to router"""
    router = Router()

    async def handler1(request: Request, response: Response):
        return response.text("test1")

    async def handler2(request: Request, response: Response):
        return response.text("test2")

    route1 = Route("/test1", handler1, methods=["GET"])
    route2 = Route("/test2", handler2, methods=["POST"])

    router.add_route(route1)
    router.add_route(route2)

    assert len(router.routes) >= 2
    assert route1 in router.routes
    assert route2 in router.routes


# ========== Integration Tests ==========


def test_basic_route_with_app(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test basic route integration with app"""
    app = NexiosApp()

    @app.get("/hello")
    async def hello(request: Request, response: Response):
        return response.text("Hello, World!")

    with test_client_factory(app) as client:
        resp = client.get("/hello")
        assert resp.status_code == 200
        assert resp.text == "Hello, World!"


def test_router_mounted_to_app(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test router mounted to application"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/users")
    async def get_users(request: Request, response: Response):
        return response.json({"users": ["Alice", "Bob"]})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/users")
        assert resp.status_code == 200
        assert resp.json() == {"users": ["Alice", "Bob"]}


def test_empty_path_converts_to_slash():
    """Test that empty path is converted to /"""

    async def handler(request: Request, response: Response):
        return response.text("root")

    route = Route("", handler, methods=["GET"])
    assert route.raw_path == "/"


def test_route_handler_must_be_callable():
    """Test that route handler must be callable"""
    with pytest.raises(AssertionError):
        Route("/test", "not-callable", methods=["GET"])


def test_router_with_multiple_prefixes(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test multiple routers with different prefixes"""
    app = NexiosApp()

    api_v1 = Router(prefix="/api/v1")
    api_v2 = Router(prefix="/api/v2")

    @api_v1.get("/status")
    async def status_v1(request: Request, response: Response):
        return response.json({"version": "1.0"})

    @api_v2.get("/status")
    async def status_v2(request: Request, response: Response):
        return response.json({"version": "2.0"})

    app.mount_router(api_v1)
    app.mount_router(api_v2)

    with test_client_factory(app) as client:
        resp_v1 = client.get("/api/v1/status")
        assert resp_v1.json() == {"version": "1.0"}

        resp_v2 = client.get("/api/v2/status")
        assert resp_v2.json() == {"version": "2.0"}
