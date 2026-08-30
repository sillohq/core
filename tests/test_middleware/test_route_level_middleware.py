"""
Tests for route-level middleware
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.core.routing import Route, Router
from sillo.testclient import TestClient

# ========== Basic Route-Level Middleware Tests ==========


def test_route_level_middleware_basic(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic route-level middleware"""
    app = SilloApp()

    executed = []

    async def route_middleware(ctx: HttpContext, call_next):
        executed.append("route_middleware")
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    route = Route("/test", handler, middleware=[route_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "route_middleware" in executed
        assert "handler" in executed


def test_route_level_middleware_isolated(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that route middleware only applies to that specific route"""
    app = SilloApp()

    executed = []

    async def route1_middleware(ctx: HttpContext, call_next):
        executed.append("route1_middleware")
        response = await call_next()
        return response

    async def handler1(ctx: HttpContext):
        return json({"route": "1"})

    async def handler2(ctx: HttpContext):
        return json({"route": "2"})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple route-level middleware"""
    app = SilloApp()

    execution_order = []

    async def middleware_1(ctx: HttpContext, call_next):
        execution_order.append("m1_before")
        response = await call_next()
        execution_order.append("m1_after")
        return response

    async def middleware_2(ctx: HttpContext, call_next):
        execution_order.append("m2_before")
        response = await call_next()
        execution_order.append("m2_after")
        return response

    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    route = Route("/test", handler, middleware=[middleware_1, middleware_2])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "m1_before" in execution_order
        assert "m2_before" in execution_order
        assert "handler" in execution_order


def test_route_level_middleware_with_decorator(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route-level middleware using decorator"""
    app = SilloApp()

    async def auth_middleware(ctx: HttpContext, call_next):
        token = ctx.headers.get("Authorization")
        if not token:
            return json({"error": "Unauthorized"}).status(401)
        response = await call_next()
        return response

    @app.route("/protected", methods=["GET"], middleware=[auth_middleware])
    async def protected_handler(ctx: HttpContext):
        return json({"message": "Protected"})

    with test_client_factory(app) as client:
        # Without auth
        resp1 = client.get("/protected")
        assert resp1.status_code == 401

        # With auth
        resp2 = client.get("/protected", headers={"Authorization": "Bearer token"})
        assert resp2.status_code == 200


def test_route_level_middleware_modifies_request(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware modifying request"""
    app = SilloApp()

    async def add_user_middleware(ctx: HttpContext, call_next):
        ctx.scope["user"] = {"id": 123, "name": "John"}
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        user = ctx.scope.get("user")
        return json(user)

    route = Route("/test", handler, middleware=[add_user_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["id"] == 123
        assert data["name"] == "John"


def test_route_level_middleware_modifies_response(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware modifying response"""
    app = SilloApp()

    async def add_header_middleware(ctx: HttpContext, call_next):
        response = await call_next()
        response.set_header("X-Route-Middleware", "applied")
        return response

    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    route = Route("/test", handler, middleware=[add_header_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-route-middleware") == "applied"


# ========== Route Middleware with App/Router Middleware Tests ==========


def test_route_with_app_middleware(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware combined with app middleware"""
    app = SilloApp()

    execution_order = []

    async def app_middleware(ctx: HttpContext, call_next):
        execution_order.append("app_before")
        response = await call_next()
        execution_order.append("app_after")
        return response

    async def route_middleware(ctx: HttpContext, call_next):
        execution_order.append("route_before")
        response = await call_next()
        execution_order.append("route_after")
        return response

    app.use(app_middleware)

    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware with both router and app middleware"""
    app = SilloApp()
    router = Router(prefix="/api")

    execution_order = []

    async def app_middleware(ctx: HttpContext, call_next):
        execution_order.append("app")
        response = await call_next()
        return response

    async def router_middleware(ctx: HttpContext, call_next):
        execution_order.append("router")
        response = await call_next()
        return response

    async def route_middleware(ctx: HttpContext, call_next):
        execution_order.append("route")
        response = await call_next()
        return response

    app.use(app_middleware)
    router.use(router_middleware)

    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware for input validation"""
    app = SilloApp()

    async def validate_query_middleware(
        ctx: HttpContext, call_next
    ):
        page = ctx.query_params.get("page")
        if page and not page.isdigit():
            return json({"error": "Invalid page parameter"}).status(400)
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        page = ctx.query_params.get("page", "1")
        return json({"page": int(page)})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware for rate limiting"""
    app = SilloApp()

    request_counts = {}

    async def rate_limit_middleware(ctx: HttpContext, call_next):
        client_ip = ctx.get_client_ip()
        count = request_counts.get(client_ip, 0)

        if count >= 3:
            return json({"error": "Rate limit exceeded"}).status(429)

        request_counts[client_ip] = count + 1
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware for response caching"""
    app = SilloApp()

    cache = {}
    call_count = {"count": 0}

    async def cache_middleware(ctx: HttpContext, call_next):
        cache_key = str(ctx.url)

        if cache_key in cache:
            return json(cache[cache_key])

        response = await call_next()
        cache[cache_key] = {"cached": True, "count": call_count["count"]}
        return response

    async def handler(ctx: HttpContext):
        call_count["count"] += 1
        return json({"cached": False, "count": call_count["count"]})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware for request logging"""
    app = SilloApp()

    logs = []

    async def logging_middleware(ctx: HttpContext, call_next):
        logs.append(
            {"method": ctx.method, "path": ctx.path, "timestamp": "2024-01-01"}
        )
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    route = Route("/test", handler, middleware=[logging_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        client.get("/test")
        assert len(logs) == 1
        assert logs[0]["method"] == "GET"
        assert logs[0]["path"] == "/test"


def test_route_middleware_different_methods(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware applies to all methods of the route"""
    app = SilloApp()

    executed = []

    async def method_logger_middleware(ctx: HttpContext, call_next):
        executed.append(ctx.method)
        response = await call_next()
        return response

    async def handler(ctx: HttpContext):
        return json({"method": ctx.method})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route middleware handling errors"""
    app = SilloApp()

    async def error_handler_middleware(ctx: HttpContext, call_next):
        try:
            response = await call_next()
        except ValueError as e:
            return json({"error": str(e), "handled": True}).status(400)
        return response

    async def handler(ctx: HttpContext):
        raise ValueError("Route-specific error")

    route = Route("/test", handler, middleware=[error_handler_middleware])
    app.router.add_route(route)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        data = resp.json()
        assert data["handled"] is True
        assert "Route-specific error" in data["error"]
