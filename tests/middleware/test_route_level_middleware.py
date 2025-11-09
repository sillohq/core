"""
Tests for route-level middleware
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient

# ========== Basic Route-Level Middleware Tests ==========


def test_route_level_middleware_basic(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test basic route-level middleware"""
    app = NexiosApp()

    executed = []

    async def route_middleware(request: Request, response: Response, call_next):
        executed.append("route_middleware")
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        executed.append("handler")
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[route_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "route_middleware" in executed
        assert "handler" in executed


def test_route_level_middleware_isolated(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that route middleware only applies to that specific route"""
    app = NexiosApp()

    executed = []

    async def route1_middleware(request: Request, response: Response, call_next):
        executed.append("route1_middleware")
        await call_next()
        return response

    async def handler1(request: Request, response: Response):
        return response.json({"route": "1"})

    async def handler2(request: Request, response: Response):
        return response.json({"route": "2"})

    route1 = Route("/route1", handler1, middleware=[route1_middleware])
    route2 = Route("/route2", handler2)

    app.router.add_route(route1)
    app.router.add_route(route2)

    with test_client_factory(app) as client:
        # Route1 should trigger middleware
        executed.clear()
        resp1 = client.get("/route1")
        assert resp1.status_code == 200
        assert "route1_middleware" in executed

        # Route2 should NOT trigger route1 middleware
        executed.clear()
        resp2 = client.get("/route2")
        assert resp2.status_code == 200
        assert "route1_middleware" not in executed


def test_route_level_middleware_multiple(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test multiple route-level middleware"""
    app = NexiosApp()

    execution_order = []

    async def middleware_1(request: Request, response: Response, call_next):
        execution_order.append("m1_before")
        await call_next()
        execution_order.append("m1_after")
        return response

    async def middleware_2(request: Request, response: Response, call_next):
        execution_order.append("m2_before")
        await call_next()
        execution_order.append("m2_after")
        return response

    async def handler(request: Request, response: Response):
        execution_order.append("handler")
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[middleware_1, middleware_2])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "m1_before" in execution_order
        assert "m2_before" in execution_order
        assert "handler" in execution_order


def test_route_level_middleware_with_decorator(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route-level middleware using decorator"""
    app = NexiosApp()

    async def auth_middleware(request: Request, response: Response, call_next):
        token = request.headers.get("Authorization")
        if not token:
            return response.status(401).json({"error": "Unauthorized"})
        await call_next()
        return response

    @app.route("/protected", methods=["GET"], middleware=[auth_middleware])
    async def protected_handler(request: Request, response: Response):
        return response.json({"message": "Protected"})

    with test_client_factory(app) as client:
        # Without auth
        resp1 = client.get("/protected")
        assert resp1.status_code == 401

        # With auth
        resp2 = client.get("/protected", headers={"Authorization": "Bearer token"})
        assert resp2.status_code == 200


def test_route_level_middleware_modifies_request(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware modifying request"""
    app = NexiosApp()

    async def add_user_middleware(request: Request, response: Response, call_next):
        request.scope["user"] = {"id": 123, "name": "John"}
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        user = request.scope.get("user")
        return response.json(user)

    route = Route("/test", handler, middleware=[add_user_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["id"] == 123
        assert data["name"] == "John"


def test_route_level_middleware_modifies_response(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware modifying response"""
    app = NexiosApp()

    async def add_header_middleware(request: Request, response: Response, call_next):
        await call_next()
        response.set_header("X-Route-Middleware", "applied")
        return response

    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[add_header_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-route-middleware") == "applied"


# ========== Route Middleware with App/Router Middleware Tests ==========


def test_route_with_app_middleware(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware combined with app middleware"""
    app = NexiosApp()

    execution_order = []

    async def app_middleware(request: Request, response: Response, call_next):
        execution_order.append("app_before")
        await call_next()
        execution_order.append("app_after")
        return response

    async def route_middleware(request: Request, response: Response, call_next):
        execution_order.append("route_before")
        await call_next()
        execution_order.append("route_after")
        return response

    app.add_middleware(app_middleware)

    async def handler(request: Request, response: Response):
        execution_order.append("handler")
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[route_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        # App middleware should execute before route middleware
        assert execution_order.index("app_before") < execution_order.index(
            "route_before"
        )
        assert execution_order.index("route_after") < execution_order.index("app_after")


def test_route_with_router_and_app_middleware(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware with both router and app middleware"""
    app = NexiosApp()
    router = Router(prefix="/api")

    execution_order = []

    async def app_middleware(request: Request, response: Response, call_next):
        execution_order.append("app")
        await call_next()
        return response

    async def router_middleware(request: Request, response: Response, call_next):
        execution_order.append("router")
        await call_next()
        return response

    async def route_middleware(request: Request, response: Response, call_next):
        execution_order.append("route")
        await call_next()
        return response

    app.add_middleware(app_middleware)
    router.add_middleware(router_middleware)

    async def handler(request: Request, response: Response):
        execution_order.append("handler")
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[route_middleware])
    router.add_route(route)
    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        # Order: app -> router -> route -> handler
        assert execution_order.index("app") < execution_order.index("router")
        assert execution_order.index("router") < execution_order.index("route")
        assert execution_order.index("route") < execution_order.index("handler")


# ========== Route Middleware Specific Use Cases ==========


def test_route_middleware_validation(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware for input validation"""
    app = NexiosApp()

    async def validate_query_middleware(
        request: Request, response: Response, call_next
    ):
        page = request.query_params.get("page")
        if page and not page.isdigit():
            return response.status(400).json({"error": "Invalid page parameter"})
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        page = request.query_params.get("page", "1")
        return response.json({"page": int(page)})

    route = Route("/items", handler, middleware=[validate_query_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        # Valid page
        resp1 = client.get("/items?page=2")
        assert resp1.status_code == 200
        assert resp1.json()["page"] == 2

        # Invalid page
        resp2 = client.get("/items?page=abc")
        assert resp2.status_code == 400


def test_route_middleware_rate_limiting(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware for rate limiting"""
    app = NexiosApp()

    request_counts = {}

    async def rate_limit_middleware(request: Request, response: Response, call_next):
        client_ip = request.get_client_ip()
        count = request_counts.get(client_ip, 0)

        if count >= 3:
            return response.status(429).json({"error": "Rate limit exceeded"})

        request_counts[client_ip] = count + 1
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    route = Route("/api/data", handler, middleware=[rate_limit_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        # First 3 requests should succeed
        for i in range(3):
            resp = client.get("/api/data")
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.get("/api/data")
        assert resp.status_code == 429


def test_route_middleware_caching(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware for response caching"""
    app = NexiosApp()

    cache = {}
    call_count = {"count": 0}

    async def cache_middleware(request: Request, response: Response, call_next):
        cache_key = str(request.url)

        if cache_key in cache:
            return response.json(cache[cache_key])

        await call_next()
        cache[cache_key] = {"cached": True, "count": call_count["count"]}
        return response

    async def handler(request: Request, response: Response):
        call_count["count"] += 1
        return response.json({"cached": False, "count": call_count["count"]})

    route = Route("/data", handler, middleware=[cache_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        # First request - not cached
        resp1 = client.get("/data")
        data1 = resp1.json()

        # Second request - should be cached
        resp2 = client.get("/data")
        data2 = resp2.json()

        assert data2["cached"] is True


def test_route_middleware_logging(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware for request logging"""
    app = NexiosApp()

    logs = []

    async def logging_middleware(request: Request, response: Response, call_next):
        logs.append(
            {"method": request.method, "path": request.path, "timestamp": "2024-01-01"}
        )
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    route = Route("/test", handler, middleware=[logging_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        client.get("/test")
        assert len(logs) == 1
        assert logs[0]["method"] == "GET"
        assert logs[0]["path"] == "/test"


def test_route_middleware_different_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware applies to all methods of the route"""
    app = NexiosApp()

    executed = []

    async def method_logger_middleware(request: Request, response: Response, call_next):
        executed.append(request.method)
        await call_next()
        return response

    async def handler(request: Request, response: Response):
        return response.json({"method": request.method})

    route = Route(
        "/test",
        handler,
        methods=["GET", "POST", "PUT"],
        middleware=[method_logger_middleware],
    )
    app.router.add_route(route)

    with test_client_factory(app) as client:
        client.get("/test")
        client.post("/test")
        client.put("/test")

        assert "GET" in executed
        assert "POST" in executed
        assert "PUT" in executed


def test_route_middleware_error_handling(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route middleware handling errors"""
    app = NexiosApp()

    async def error_handler_middleware(request: Request, response: Response, call_next):
        try:
            await call_next()
        except ValueError as e:
            return response.status(400).json({"error": str(e), "handled": True})
        return response

    async def handler(request: Request, response: Response):
        raise ValueError("Route-specific error")

    route = Route("/test", handler, middleware=[error_handler_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        data = resp.json()
        assert data["handled"] is True
        assert "Route-specific error" in data["error"]
